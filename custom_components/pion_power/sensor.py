"""Sensor platform for Pion Power."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HOME_SENSORS, SENSORS
from .entity import PionBaseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [PionSensor(coordinator, entry, d) for d in SENSORS]
    if coordinator.device_code:
        entities += [PionHomeSensor(coordinator, entry, d) for d in HOME_SENSORS]
    async_add_entities(entities)


class _Base(PionBaseEntity, SensorEntity):
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


class PionSensor(_Base):
    """A live-data value from GetRealDataByStationCode."""

    @property
    def native_value(self):
        return self.coordinator.data.get("real", {}).get(self._key)


class PionHomeSensor(_Base):
    """A daily-energy value from GetHomeData (value is nested under 'Value')."""

    @property
    def native_value(self):
        item = self.coordinator.data.get("home", {}).get(self._key)
        if isinstance(item, dict):
            item = item.get("Value")
        try:
            return float(item)
        except (TypeError, ValueError):
            return None
