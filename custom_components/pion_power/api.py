"""Async client for the Pion Power (Hoymiles HAS) cloud API."""
from __future__ import annotations

import hashlib
import json
import logging
from urllib.parse import quote

import aiohttp

from .const import BASE_URL, COMPANY_CODE

_LOGGER = logging.getLogger(__name__)


class PionAuthError(Exception):
    """Raised when authentication fails."""


class PionApiError(Exception):
    """Raised on a non-success API response."""


class PionClient:
    """Minimal async client. Auth is a 'token' header + 'companycode'; no request signing."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._token: str | None = None
        self._userinfo: dict | None = None

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
        async with self._session.post(
            BASE_URL + path, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            return await resp.json(content_type=None)

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
        self._userinfo = {
            "UserLoginId": d.get("UserId"),
            "UserName": d.get("UserName"),
            "Role": d.get("RoleId"),
            "Email": self._email,
        }
        return d

    async def _call(self, path: str, body: dict) -> dict:
        """POST with one automatic re-login if the token has expired (Code -1)."""
        data = await self._post(path, body)
        if str(data.get("Code")) == "-1":
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

    async def get_workmode(self, station: str) -> dict:
        data = await self._call(
            "APPInterfaceServer/DeviceParam/GetStationWorkMode", {"StationCode": station}
        )
        return data.get("Data") or {}

    async def set_workmode_field(self, station: str, field: str, value: int) -> None:
        """Read the full work-mode object, change one field, write it back."""
        current = await self.get_workmode(station)
        if not current:
            raise PionApiError("could not read current work mode")
        payload = dict(current)
        payload[field] = value
        res = await self._call("APPInterfaceServer/DeviceParam/SetStationWorkMode", payload)
        if str(res.get("Code")) != "1":
            raise PionApiError(res.get("Msg", "set work mode failed"))
