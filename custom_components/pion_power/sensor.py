"""Sensor platform for Pion Power."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HOME_SENSORS, SENSORS
from .entity import PionBaseEntity
from .schedule import humanize_groups, humanize_period, template_groups


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


class PionTouScheduleSensor(PionBaseEntity, SensorEntity):
    """Surfaces the active Time-of-Use schedule (any shape).

    Reads the active TOU *template* (the full, app-editable schedule) and
    represents it faithfully regardless of complexity — multiple seasonal date
    ranges, separate weekday/weekend rules, special days. State = total number
    of time periods across all rule-groups. Falls back to the workmode's
    compiled period list only if no template is available.
    """

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "TOU Schedule"
        self._attr_unique_id = f"{entry.entry_id}_tou_schedule"

    @property
    def _template(self) -> dict:
        return self.coordinator.data.get("template", {}) or {}

    @property
    def _groups(self) -> list[dict]:
        return template_groups(self._template)

    @property
    def native_value(self):
        groups = self._groups
        if groups:
            return sum(len(g["periods"]) for g in groups)
        wm = self.coordinator.data.get("workmode", {}) or {}
        wm_periods = wm.get("TOUModeStraPeriods")
        return len(wm_periods) if isinstance(wm_periods, list) else 0

    @property
    def extra_state_attributes(self):
        wm = self.coordinator.data.get("workmode", {}) or {}
        template = self._template
        groups = self._groups
        special = template.get("StraSpecialDayInfos") or []

        if groups:
            source = "template"
            # Convenience flat list for the simple single-group case.
            periods = groups[0]["periods"] if len(groups) == 1 else [
                p for g in groups for p in g["periods"]
            ]
            summary = humanize_groups(groups)
        else:
            source = "workmode"
            wm_periods = wm.get("TOUModeStraPeriods")
            periods = wm_periods if isinstance(wm_periods, list) else []
            summary = [humanize_period(p) for p in periods]

        return {
            "tou_mode_active": str(wm.get("EmsMode")) == "7",
            "ems_mode": wm.get("EmsMode"),
            "reserved_soc": wm.get("TOUModeReservedSoc"),
            "template_name": template.get("_TemplateName") or template.get("TemplateName"),
            "source": source,
            "group_count": len(groups),
            "special_day_count": len(special),
            "summary": summary,
            "groups": groups,
            "periods": periods,
        }
