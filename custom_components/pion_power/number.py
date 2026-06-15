"""Number platform: work-mode controls + per-period schedule fields."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROLS, DOMAIN
from .entity import PionBaseEntity, PionPeriodEntity, setup_period_entities

# Per-period numeric fields: (draft key, name, unit).
PERIOD_NUMBERS = [
    ("SOC", "Target SOC", "%"),
    ("RunPower", "Run Power", "%"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(PionNumber(coordinator, entry, definition) for definition in CONTROLS)

    def _factory(coord, ent, index):
        return [
            PionPeriodNumber(coord, ent, index, key, name, unit)
            for key, name, unit in PERIOD_NUMBERS
        ]

    setup_period_entities(coordinator, entry, async_add_entities, _factory)


class PionNumber(PionBaseEntity, NumberEntity):
    """A writable work-mode parameter.

    NOTE: parameters are mode-gated by EmsMode and apply asynchronously (~8s);
    the value refreshes on the next coordinator poll.
    """

    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, entry, definition: dict) -> None:
        super().__init__(coordinator, entry)
        self._field = definition["field"]
        self._attr_name = definition["name"]
        self._attr_unique_id = f"{entry.entry_id}_{self._field}"
        self._attr_native_min_value = definition["min"]
        self._attr_native_max_value = definition["max"]
        self._attr_native_step = definition["step"]
        if definition.get("unit"):
            self._attr_native_unit_of_measurement = definition["unit"]

    @property
    def native_value(self) -> float | None:
        val = self.coordinator.data.get("workmode", {}).get(self._field)
        return None if val is None else float(val)

    async def async_set_native_value(self, value: float) -> None:
        if not self.coordinator.allow_write:
            raise HomeAssistantError(
                "Schedule writing is disabled. Enable 'Allow schedule writes' in "
                "the Pion Power integration options once your system is healthy."
            )
        await self.coordinator.client.set_workmode_field(
            self.coordinator.station, self._field, int(value)
        )
        await self.coordinator.async_request_refresh()


class PionPeriodNumber(PionPeriodEntity, NumberEntity):
    """A numeric field of one TOU period (edits the draft; commit via Apply)."""

    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator, entry, index, key, name, unit) -> None:
        super().__init__(coordinator, entry, index)
        self._field = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_period_{index}_{key}"
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> float | None:
        period = self._period
        if period is None:
            return None
        val = period.get(self._field)
        return None if val is None else float(val)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.edit_period(self._index, self._field, int(value))
