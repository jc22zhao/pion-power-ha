"""Number platform for Pion Power work-mode controls (read-modify-write)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROLS, DOMAIN
from .entity import PionBaseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(PionNumber(coordinator, entry, definition) for definition in CONTROLS)


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
        await self.coordinator.client.set_workmode_field(
            self.coordinator.station, self._field, int(value)
        )
        await self.coordinator.async_request_refresh()
