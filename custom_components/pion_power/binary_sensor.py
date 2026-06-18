"""Binary sensor platform for Pion Power."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import PionBaseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [PionOnline(coordinator, entry), PionGridPower(coordinator, entry)]
    )


class PionOnline(PionBaseEntity, BinarySensorEntity):
    """Whether the HEMS is reporting online."""

    _attr_name = "HEMS Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_online"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("real", {}).get("IsOnline"))


class PionGridPower(PionBaseEntity, BinarySensorEntity):
    """Grid power present. ON = grid available, OFF = grid outage/blackout, read
    from the inverter's grid-outage flag (signal 10271047; 1 = outage). Goes
    unavailable when the device feed isn't reporting (e.g. a blackout that also
    takes the DTU's internet down), so it never shows a stale 'grid present'."""

    _attr_name = "Grid Power"
    _attr_device_class = BinarySensorDeviceClass.POWER
    _GRID_OUTAGE_SIGNAL = "10271047"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_grid_power"

    @property
    def _value(self):
        item = self.coordinator.data.get("device", {}).get(self._GRID_OUTAGE_SIGNAL)
        return item.get("SignalValue") if isinstance(item, dict) else None

    @property
    def available(self) -> bool:
        return super().available and self._value is not None

    @property
    def is_on(self) -> bool | None:
        val = self._value
        if val is None:
            return None
        return float(val) < 0.5
