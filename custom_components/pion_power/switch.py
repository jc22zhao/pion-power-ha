"""Switch platform: manually hand the single session to the mobile app."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import PionBaseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PionCloudConnectionSwitch(coordinator, entry)])


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
