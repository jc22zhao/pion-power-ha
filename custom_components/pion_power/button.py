"""Button platform: add a charge window (hub) / delete a charge window."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_CHARGE_WINDOWS
from .entity import PionBaseEntity, PionWindowEntity, setup_window_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PionAddWindowButton(coordinator, entry)])

    def _factory(coord, ent, index):
        return [PionDeleteWindowButton(coord, ent, index)]

    setup_window_entities(coordinator, entry, async_add_entities, _factory)


class PionAddWindowButton(PionBaseEntity, ButtonEntity):
    """Append a new charge window (capped at the inverter's max)."""

    _attr_name = "Add charge window"
    _attr_icon = "mdi:plus-box"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_add_window"

    @property
    def available(self) -> bool:
        return super().available and len(self.coordinator.get_windows()) < MAX_CHARGE_WINDOWS

    async def async_press(self) -> None:
        self.coordinator.add_window()


class PionDeleteWindowButton(PionWindowEntity, ButtonEntity):
    """Remove this charge window."""

    _attr_name = "Delete window"
    _attr_icon = "mdi:delete"

    def __init__(self, coordinator, entry, index) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_unique_id = f"{entry.entry_id}_window_{index}_delete"

    async def async_press(self) -> None:
        self.coordinator.delete_window(self._index)
