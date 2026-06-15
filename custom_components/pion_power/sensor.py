"""Sensor platform for Pion Power."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SENSORS
from .entity import PionBaseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(PionSensor(coordinator, entry, definition) for definition in SENSORS)


class PionSensor(PionBaseEntity, SensorEntity):
    """A single live-data value."""

    def __init__(self, coordinator, entry, definition: dict) -> None:
        super().__init__(coordinator, entry)
        self._key = definition["key"]
        self._attr_name = definition["name"]
        self._attr_unique_id = f"{entry.entry_id}_{self._key}"
        self._attr_native_unit_of_measurement = definition.get("unit")
        if definition.get("device_class"):
            self._attr_device_class = definition["device_class"]
        if definition.get("state_class"):
            self._attr_state_class = definition["state_class"]

    @property
    def native_value(self):
        return self.coordinator.data.get("real", {}).get(self._key)
