"""Data update coordinator for Pion Power."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PionClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PionCoordinator(DataUpdateCoordinator):
    """Polls live data and work-mode for one station."""

    def __init__(self, hass: HomeAssistant, client: PionClient, station: str, interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.station = station

    async def _async_update_data(self) -> dict:
        try:
            real = await self.client.get_realdata(self.station)
            workmode = await self.client.get_workmode(self.station)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Error communicating with Pion API: {err}") from err
        return {"real": real, "workmode": workmode}
