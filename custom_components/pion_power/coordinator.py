"""Data update coordinator for Pion Power, with single-session coexistence."""
from __future__ import annotations

import logging
import time
from copy import deepcopy
from datetime import timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import PionApiError, PionAuthError, PionClient, PionKicked
from .const import DOMAIN, MAX_CHARGE_WINDOWS, WRITE_DEBOUNCE
from .schedule import blank_period, draft_to_workmode, workmode_draft

_LOGGER = logging.getLogger(__name__)


class PionCoordinator(DataUpdateCoordinator):
    """Polls live data, work-mode and daily-energy for one station.

    Coexists with the mobile app on the single-session account:
    - `paused` (manual switch): HA does not touch the cloud at all.
    - auto-yield: if the app grabs the session, HA backs off `retry_interval`
      seconds before reclaiming, instead of immediately fighting for it.
    """

    def __init__(
        self, hass: HomeAssistant, client: PionClient, station: str,
        interval: int, retry_interval: int, device_code: str | None = None,
        allow_write: bool = False,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=interval))
        self.client = client
        self.station = station
        self.device_code = device_code
        self.retry_interval = retry_interval
        self.allow_write = allow_write
        self.paused = False
        self._yield_until = 0.0
        self._reclaim = False
        # Charge-window editor model. `_windows` mirrors the work-mode charge
        # windows; edits mutate it and schedule a single debounced write.
        self._windows: list[dict] | None = None
        self._windows_pending = False
        self._write_unsub = None

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False
        self._yield_until = 0.0
        self._reclaim = True

    def _keep(self) -> dict:
        return self.data or {"real": {}, "device": {}, "workmode": {}, "home": {}, "template": {}}

    # ------------------------------------------------------------------ #
    # Charge-window editor (work-mode TOUModeStraPeriods, debounced auto-write)
    # ------------------------------------------------------------------ #
    def _workmode(self) -> dict:
        return (self.data or {}).get("workmode", {}) or {}

    def get_windows(self) -> list[dict]:
        """Charge windows from the work mode. Tracks the cloud until the user (or
        an automation) edits a window, then holds the local copy until the
        debounced write flushes — so polls don't clobber an in-progress edit."""
        if self._windows is None or not self._windows_pending:
            self._windows = workmode_draft(self._workmode())[:MAX_CHARGE_WINDOWS]
        return self._windows

    @callback
    def _schedule_write(self) -> None:
        self._windows_pending = True
        self.async_update_listeners()
        if self._write_unsub:
            self._write_unsub()
        self._write_unsub = async_call_later(self.hass, WRITE_DEBOUNCE, self._flush_windows)

    async def _flush_windows(self, _now=None) -> None:
        self._write_unsub = None
        windows = self._windows or []
        if not self.allow_write:
            _LOGGER.warning(
                "Charge-window edit not written: 'Allow schedule writes' is off"
            )
        else:
            try:
                await self.client.set_tou_schedule(
                    self.station, draft_to_workmode(windows), ensure_tou_mode=True
                )
            except PionApiError as err:
                _LOGGER.error("Pion charge-window write failed: %s", err)
        self._windows_pending = False
        await self.async_request_refresh()

    def edit_window(self, index: int, field: str, value) -> None:
        windows = self.get_windows()
        if 0 <= index < len(windows):
            windows[index][field] = value
            self._schedule_write()

    def add_window(self) -> None:
        windows = self.get_windows()
        if len(windows) >= MAX_CHARGE_WINDOWS:
            _LOGGER.warning("Inverter supports at most %s charge windows", MAX_CHARGE_WINDOWS)
            return
        windows.append(blank_period())
        self._schedule_write()

    def delete_window(self, index: int) -> None:
        windows = self.get_windows()
        if 0 <= index < len(windows):
            windows.pop(index)
            self._schedule_write()

    async def _fetch_active_template(self) -> dict:
        """Best-effort: the active TOU template's full detail (the real schedule).

        Returns {} on any failure so it never breaks the live-data update.
        """
        try:
            tpls = await self.client.get_station_tou_templates(self.station)
            stations = tpls.get("StationTous") or []
            active = next((t for t in stations if t.get("StraEn")), None)
            if not active or not active.get("TemplateId"):
                return {}
            detail = await self.client.get_tou_template_detail(active["TemplateId"])
            if detail:
                detail["_TemplateName"] = active.get("TemplateName")
            return detail or {}
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Pion TOU template fetch failed (non-fatal): %s", err)
            return self._keep().get("template", {}) or {}

    async def _async_update_data(self) -> dict:
        now = time.time()
        if self.paused or now < self._yield_until:
            return self._keep()
        try:
            if self._reclaim:
                await self.client.login()
                self._reclaim = False
            real = await self.client.get_realdata(self.station)
            device = {}
            if self.device_code:
                device = await self.client.get_device_realdata(self.device_code)
            workmode = await self.client.get_workmode(self.station)
            template = await self._fetch_active_template()
            home = {}
            if self.device_code:
                date = dt_util.now().strftime("%Y-%m-%d")
                home = await self.client.get_home_data(self.device_code, date)
        except PionKicked:
            self._yield_until = time.time() + self.retry_interval
            self._reclaim = True
            _LOGGER.info(
                "Pion session taken by another client (mobile app); yielding %ss before reclaiming",
                self.retry_interval,
            )
            return self._keep()
        except PionAuthError as err:
            # Credentials no longer valid (e.g. password changed) -> prompt reauth.
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Error communicating with Pion API: {err}") from err
        return {"real": real, "device": device, "workmode": workmode, "home": home, "template": template}
