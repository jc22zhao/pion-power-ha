"""Switch platform: session control + per-charge-window grid-charge toggle."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import PionBaseEntity, PionWindowEntity, setup_window_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PionCloudConnectionSwitch(coordinator, entry)])

    def _factory(coord, ent, index):
        return [PionWindowGridChargeSwitch(coord, ent, index)]

    setup_window_entities(coordinator, entry, async_add_entities, _factory)


class PionCloudConnectionSwitch(PionBaseEntity, SwitchEntity):
    """ON = HA stays connected (polls/controls the cloud).
    OFF = HA releases the session so you can use the Pion mobile app uninterrupted."""

    _attr_name = "Cloud Connection"
    _attr_icon = "mdi:cloud-sync"
    _attr_entity_category = None

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_cloud_connection"

    @property
    def is_on(self) -> bool:
        return not self.coordinator.paused

    @property
    def available(self) -> bool:
        return True  # stays controllable even while paused / data is stale

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.resume()
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.pause()
        self.async_write_ha_state()


class PionWindowGridChargeSwitch(PionWindowEntity, SwitchEntity):
    """Whether one charge window charges from the grid (vs solar only)."""

    _attr_name = "Grid Charge"
    _attr_icon = "mdi:transmission-tower-import"

    def __init__(self, coordinator, entry, index) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_unique_id = f"{entry.entry_id}_window_{index}_gridcharge"

    @property
    def is_on(self) -> bool | None:
        window = self._window
        return None if window is None else bool(window.get("GridChargeEn"))

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.edit_window(self._index, "GridChargeEn", True)

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.edit_window(self._index, "GridChargeEn", False)
