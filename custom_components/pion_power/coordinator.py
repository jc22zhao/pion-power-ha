"""Data update coordinator for Pion Power, with single-session coexistence."""
from __future__ import annotations

import logging
import time
from copy import deepcopy
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import PionApiError, PionAuthError, PionClient, PionKicked
from .const import DOMAIN
from .schedule import (
    apply_periods_to_template,
    blank_period,
    primary_periods,
    workmode_charge_periods,
)

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
        # Staging buffer for the per-period editor entities. None => track the
        # server. Once edited, `_draft_dirty` holds it until Apply or Reload.
        self._draft: list[dict] | None = None
        self._draft_dirty = False

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False
        self._yield_until = 0.0
        self._reclaim = True

    def _keep(self) -> dict:
        return self.data or {"real": {}, "device": {}, "workmode": {}, "home": {}, "template": {}}

    # ------------------------------------------------------------------ #
    # Schedule editor draft (used by the per-period editor entities)
    # ------------------------------------------------------------------ #
    @property
    def draft_dirty(self) -> bool:
        return self._draft_dirty

    def _active_template(self) -> dict:
        return (self.data or {}).get("template", {}) or {}

    def get_draft(self) -> list[dict]:
        """Editable period list for the active template's primary group. Tracks
        the server until the user edits, then holds the draft until Apply/Reload."""
        if self._draft is None or not self._draft_dirty:
            self._draft = primary_periods(self._active_template())
        return self._draft

    def _touch(self) -> None:
        self._draft_dirty = True
        self.async_update_listeners()

    def edit_period(self, index: int, field: str, value) -> None:
        draft = self.get_draft()
        if 0 <= index < len(draft):
            draft[index][field] = value
            self._touch()

    def add_period(self) -> None:
        self.get_draft().append(blank_period())
        self._touch()

    def delete_period(self, index: int) -> None:
        draft = self.get_draft()
        if 0 <= index < len(draft):
            draft.pop(index)
            self._touch()

    def reload_draft(self) -> None:
        self._draft = None
        self._draft_dirty = False
        self.async_update_listeners()

    async def apply_draft(self) -> None:
        """Write the staged schedule to the active template and activate it."""
        if not self.allow_write:
            raise PionApiError(
                "Schedule writing is disabled. Enable 'Allow schedule writes' in "
                "the Pion Power integration options once your system is healthy."
            )
        draft = self.get_draft()
        template = self._active_template()
        payload = apply_periods_to_template(template, draft)
        template_id = payload.get("TemplateId")
        await self.client.add_or_update_template(payload)
        if template_id:
            await self.client.choose_tou_template(self.station, template_id)
        # The inverter executes the workmode, not the template — push the
        # grid-charge windows so the edited schedule actually takes effect.
        await self.client.set_tou_schedule(
            self.station, workmode_charge_periods(draft), ensure_tou_mode=True
        )
        self._draft = None
        self._draft_dirty = False
        await self.async_request_refresh()

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
