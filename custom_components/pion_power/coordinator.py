"""Data update coordinator for Pion Power, with single-session coexistence."""
from __future__ import annotations

import logging
import time
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import PionClient, PionKicked
from .const import DOMAIN

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
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=interval))
        self.client = client
        self.station = station
        self.device_code = device_code
        self.retry_interval = retry_interval
        self.paused = False
        self._yield_until = 0.0
        self._reclaim = False

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False
        self._yield_until = 0.0
        self._reclaim = True

    def _keep(self) -> dict:
        return self.data or {"real": {}, "workmode": {}, "home": {}}

    async def _async_update_data(self) -> dict:
        now = time.time()
        if self.paused or now < self._yield_until:
            return self._keep()
        try:
            if self._reclaim:
                await self.client.login()
                self._reclaim = False
            real = await self.client.get_realdata(self.station)
            workmode = await self.client.get_workmode(self.station)
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
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Error communicating with Pion API: {err}") from err
        return {"real": real, "workmode": workmode, "home": home}
