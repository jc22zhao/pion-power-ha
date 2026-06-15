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
    entities.append(PionTouScheduleSensor(coordinator, entry))
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


def _humanize_period(p: dict) -> str:
    """One-line summary of a TOU period for display."""
    action = {1: "charge", 2: "discharge"}.get(p.get("ChargeOrDis"), "?")
    parts = [
        f"{p.get('StartTime', '?')}-{p.get('EndTime', '?')}",
        f"{action} to {p.get('SOC', '?')}%",
        f"@{p.get('RunPower', '?')}% power",
    ]
    if p.get("GridChargeEn"):
        parts.append("grid-charge ON")
    if p.get("SellGridEn"):
        parts.append("sell-to-grid ON")
    return "  ".join(parts)


class PionTouScheduleSensor(PionBaseEntity, SensorEntity):
    """Surfaces the server-side Time-of-Use schedule.

    State = number of configured TOU periods. Attributes hold the full schedule
    (raw + humanized), the reserved SOC, and whether TOU mode is currently active
    (EmsMode 7). Modify it with the `pion_power.set_tou_schedule` service.
    """

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "TOU Schedule"
        self._attr_unique_id = f"{entry.entry_id}_tou_schedule"

    @property
    def _periods(self) -> list[dict]:
        wm = self.coordinator.data.get("workmode", {}) or {}
        periods = wm.get("TOUModeStraPeriods")
        return periods if isinstance(periods, list) else []

    @property
    def native_value(self):
        return len(self._periods)

    @property
    def extra_state_attributes(self):
        wm = self.coordinator.data.get("workmode", {}) or {}
        periods = self._periods
        return {
            "tou_mode_active": str(wm.get("EmsMode")) == "7",
            "ems_mode": wm.get("EmsMode"),
            "reserved_soc": wm.get("TOUModeReservedSoc"),
            "summary": [_humanize_period(p) for p in periods],
            "periods": periods,
        }
