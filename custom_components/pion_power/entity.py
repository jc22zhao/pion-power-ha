"""Shared base entity for Pion Power."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
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
