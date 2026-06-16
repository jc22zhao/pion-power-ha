"""Number platform: reserve floor (hub) + per-charge-window target SOC."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROLS, DOMAIN
from .entity import PionBaseEntity, PionWindowEntity, setup_window_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    # Hub-level work-mode number(s): just the reserve floor.
    async_add_entities(PionNumber(coordinator, entry, definition) for definition in CONTROLS)

    def _factory(coord, ent, index):
        return [PionWindowSocNumber(coord, ent, index)]

    setup_window_entities(coordinator, entry, async_add_entities, _factory)


class PionNumber(PionBaseEntity, NumberEntity):
    """A writable work-mode field (the reserve floor). Applies asynchronously
    (~8s); refreshes on the next poll."""

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


class PionWindowSocNumber(PionWindowEntity, NumberEntity):
    """Target charge SOC for one charge window (debounced auto-write)."""

    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_name = "Target SOC"

    def __init__(self, coordinator, entry, index) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_unique_id = f"{entry.entry_id}_window_{index}_soc"

    @property
    def native_value(self) -> float | None:
        window = self._window
        if window is None:
            return None
        val = window.get("SOC")
        return None if val is None else float(val)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.edit_window(self._index, "SOC", int(value))
