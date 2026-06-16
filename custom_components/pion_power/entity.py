"""Shared base entity for Pion Power."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PionCoordinator


class PionBaseEntity(CoordinatorEntity[PionCoordinator]):
    """Base entity that ties everything to one HEMS device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PionCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Pion Power HEMS",
            manufacturer="Pion Power / Hoymiles",
            model="HAS-7.6LV-USG1",
        )


class PionWindowEntity(CoordinatorEntity[PionCoordinator]):
    """Base for an entity that edits one charge window (its own sub-device)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PionCoordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._index = index
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_window_{index}")},
            name=f"Charge Window {index + 1}",
            manufacturer="Pion Power / Hoymiles",
            model="Charge window",
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def _window(self) -> dict | None:
        windows = self.coordinator.get_windows()
        return windows[self._index] if 0 <= self._index < len(windows) else None

    @property
    def available(self) -> bool:
        return super().available and self._window is not None


def setup_window_entities(
    coordinator: PionCoordinator,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    factory: Callable[[PionCoordinator, ConfigEntry, int], list[Entity]],
) -> None:
    """Create per-window entities to match the current charge-window count,
    adding more as windows are added (dynamic). Entities for removed windows
    stay registered but report unavailable."""
    created: set[int] = set()

    @callback
    def _sync() -> None:
        new: list[Entity] = []
        for i in range(len(coordinator.get_windows())):
            if i not in created:
                created.add(i)
                new.extend(factory(coordinator, entry, i))
        if new:
            async_add_entities(new)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))
