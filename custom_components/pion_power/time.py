"""Time platform: start/end of each charge window (debounced auto-write)."""
from __future__ import annotations

from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import PionWindowEntity, setup_window_entities

# (draft key, name)
WINDOW_TIMES = [
    ("StartTime", "Start"),
    ("EndTime", "End"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]

    def _factory(coord, ent, index):
        return [PionWindowTime(coord, ent, index, key, name) for key, name in WINDOW_TIMES]

    setup_window_entities(coordinator, entry, async_add_entities, _factory)


def _parse_hhmm(value) -> dt_time | None:
    if not isinstance(value, str) or ":" not in value:
        return None
    try:
        hh, mm = value.split(":")[:2]
        return dt_time(int(hh) % 24, int(mm) % 60)
    except (TypeError, ValueError):
        return None


class PionWindowTime(PionWindowEntity, TimeEntity):
    """Start/End time of one charge window."""

    def __init__(self, coordinator, entry, index, key, name) -> None:
        super().__init__(coordinator, entry, index)
        self._field = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_window_{index}_{key}"

    @property
    def native_value(self) -> dt_time | None:
        window = self._window
        return None if window is None else _parse_hhmm(window.get(self._field))

    async def async_set_value(self, value: dt_time) -> None:
        self.coordinator.edit_window(
            self._index, self._field, f"{value.hour:02d}:{value.minute:02d}"
        )
