"""Async client for the Pion Power (Hoymiles HAS) cloud API."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from urllib.parse import quote

import aiohttp

from .const import BASE_URL, COMPANY_CODE

_LOGGER = logging.getLogger(__name__)


class PionAuthError(Exception):
    """Raised when authentication fails (bad credentials)."""


class PionApiError(Exception):
    """Raised on a non-success API response."""


class PionKicked(Exception):
    """Raised when our session was taken by another client (e.g. the mobile app)
    while our token should still have been valid."""


class PionClient:
    """Minimal async client. Auth = 'token' + 'companycode' headers; no request signing.

    Tracks the token's expected expiry so the caller can distinguish a normal
    token expiry (re-login immediately) from being kicked off by another client
    that logged into the same single-session account (yield instead of fighting)."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._token: str | None = None
        self._userinfo: dict | None = None
        self._expires_at: float = 0.0  # epoch seconds our token should remain valid until

    async def _post(self, path: str, body: dict, auth: bool = True) -> dict:
        headers = {
            "Content-Type": "application/json",
            "companycode": COMPANY_CODE,
            "Timezone": "UTC",
            "language": "en",
        }
        if auth and self._token:
            headers["token"] = self._token
            if self._userinfo:
                headers["userInfo"] = quote(json.dumps(self._userinfo))
        try:
            async with self._session.post(
                BASE_URL + path, json=body, headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (401, 402):
                    return {"Code": resp.status}
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            return {"Code": None, "Msg": str(err)}

    @staticmethod
    def _is_auth_error(data: dict) -> bool:
        if not isinstance(data, dict):
            return True
        return str(data.get("Code")) in ("-1", "401", "402")

    async def login(self) -> dict:
        body = {
            "UserLoginId": self._email,
            "PassWord": hashlib.md5(self._password.encode()).hexdigest(),
        }
        data = await self._post("APPInterfaceServer/Auth/UserLogin", body, auth=False)
        if str(data.get("Code")) != "1":
            raise PionAuthError(data.get("Msg", "login failed"))
        d = data["Data"]
        self._token = d.get("Token")
        try:
            eff = int(d.get("EffectiveMinites") or 0)
        except (TypeError, ValueError):
            eff = 0
        # subtract a 60s safety margin; 0 means "unknown TTL"
        self._expires_at = (time.time() + eff * 60 - 60) if eff > 1 else 0.0
        self._userinfo = {
            "UserLoginId": d.get("UserId"),
            "UserName": d.get("UserName"),
            "Role": d.get("RoleId"),
            "Email": self._email,
        }
        _LOGGER.debug("Pion login OK; token TTL ~%s min", eff)
        return d

    async def _call(self, path: str, body: dict) -> dict:
        data = await self._post(path, body)
        if self._is_auth_error(data):
            # Our token was rejected. If it should still be valid, another client
            # (the mobile app) grabbed the single session -> signal a kick.
            if self._expires_at and time.time() < self._expires_at:
                raise PionKicked()
            # Otherwise it's a normal expiry: re-login and retry once.
            await self.login()
            data = await self._post(path, body)
        return data

    async def get_stations(self) -> list[dict]:
        data = await self._call("AppInterfaceServer/Config/GetStationList", {})
        return data.get("Data") or []

    async def get_realdata(self, station: str) -> dict:
        data = await self._call(
            "AppInterfaceServer/RealData/GetRealDataByStationCode", {"StationCode": station}
        )
        return data.get("Data") or {}

    async def get_device_realdata(self, device_code: str) -> dict:
        """Per-signal real-time data from the inverter itself (the app's accurate
        'inverter' view). Returns {signal_id: {SignalValue, SignalName, ...}}.
        More accurate than the station aggregate, which over-reports PV."""
        data = await self._call(
            "AppInterfaceServer/RealData/GetRealDataByDeviceCode", {"DeviceCode": device_code}
        )
        return data.get("Data") or {}

    async def get_workmode(self, station: str) -> dict:
        data = await self._call(
            "APPInterfaceServer/DeviceParam/GetStationWorkMode", {"StationCode": station}
        )
        return data.get("Data") or {}

    async def set_workmode_field(self, station: str, field: str, value: int) -> None:
        current = await self.get_workmode(station)
        if not current:
            raise PionApiError("could not read current work mode")
        payload = dict(current)
        payload[field] = value
        res = await self._call("APPInterfaceServer/DeviceParam/SetStationWorkMode", payload)
        if str(res.get("Code")) != "1":
            raise PionApiError(res.get("Msg", "set work mode failed"))

    async def set_tou_schedule(
        self, station: str, periods: list[dict],
        reserved_soc: int | None = None, ensure_tou_mode: bool = True,
    ) -> None:
        """Write the Time-of-Use schedule server-side (persists on the inverter).

        periods: list of {StartTime, EndTime, ChargeOrDis(1=charge,2=discharge),
        SOC, RunPower, GridChargeEn, SellGridEn}."""
        current = await self.get_workmode(station)
        if not current:
            raise PionApiError("could not read current work mode")
        payload = dict(current)
        if ensure_tou_mode:
            payload["EmsMode"] = 7  # TOU
        if reserved_soc is not None:
            payload["TOUModeReservedSoc"] = int(reserved_soc)
        payload["TOUModeStraPeriods"] = periods
        res = await self._call("APPInterfaceServer/DeviceParam/SetStationWorkMode", payload)
        if str(res.get("Code")) != "1":
            raise PionApiError(res.get("Msg", "set TOU schedule failed"))

    async def get_station_tou_templates(self, station: str) -> dict:
        """Station's TOU templates. The active one has StraEn=true; its TemplateId
        feeds get_tou_template_detail for the full multi-period schedule."""
        data = await self._call(
            "AppInterfaceServer/EsStrategy/GetStationTouTemplateList", {"StationCode": station}
        )
        return data.get("Data") or {}

    async def get_tou_template_detail(self, template_id: str) -> dict:
        """Full definition of a TOU template (the complete app-editable schedule).

        Structure: StraDayPeriods[] -> StraWeekInfos[] -> StraTimePeriods[], each
        period {StartTime, EndTime, RunPower(% x100), SOC, ChargeOrDis, GridChargeEn,
        SellGridEn}. This is the real schedule; the workmode's TOUModeStraPeriods is
        only a server-compiled subset (the grid-charge windows)."""
        data = await self._call(
            "AppInterfaceServer/EsStrategy/GetTouTemplateDetail", {"TemplateId": template_id}
        )
        return data.get("Data") or {}

    async def add_or_update_template(self, template: dict) -> dict:
        """Create/update a customer TOU template. `template` mirrors the object
        returned by get_tou_template_detail (CompanyCode, TemplateId, TemplateName,
        StraDayPeriods, StraSpecialDayInfos, ...). RunPower in periods is percent
        x100, as the API expects. Returns the API Data (incl. the TemplateId)."""
        res = await self._call(
            "AppInterfaceServer/EsStrategy/AddOrUpdateCustomerStraTemplate", template
        )
        if str(res.get("Code")) != "1":
            raise PionApiError(res.get("Msg", "add/update template failed"))
        return res.get("Data") or {}

    async def choose_tou_template(self, station: str, template_id: str) -> None:
        """Activate a TOU template for a station (StraEn true on it, others off)."""
        res = await self._call(
            "AppInterfaceServer/EsStrategy/ChooseTouTemplate",
            {"StationCode": station, "TemplateId": template_id},
        )
        if str(res.get("Code")) != "1":
            raise PionApiError(res.get("Msg", "choose template failed"))

    async def get_devices(self, station: str) -> list[dict]:
        data = await self._call("AppInterfaceServer/Config/GetDeviceList", {"StationCode": station})
        return data.get("Data") or []

    async def get_home_data(self, device_code: str, date: str) -> dict:
        """Today's daily-energy breakdown (FromGrid, ToGrid, StationUse, ...)."""
        data = await self._call(
            "APPInterfaceServer/AppStatistics/GetHomeData",
            {"deviceCode": device_code, "timeType": "1", "searchTime": date},
        )
        return data.get("Data") or {}
