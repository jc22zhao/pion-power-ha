"""Button platform: apply / reload / add / delete for the TOU schedule editor."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PionApiError
from .const import DOMAIN
from .entity import PionBaseEntity, PionPeriodEntity, setup_period_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PionApplyButton(coordinator, entry),
            PionReloadButton(coordinator, entry),
            PionAddPeriodButton(coordinator, entry),
        ]
    )

    def _factory(coord, ent, index):
        return [PionDeletePeriodButton(coord, ent, index)]

    setup_period_entities(coordinator, entry, async_add_entities, _factory)


class PionApplyButton(PionBaseEntity, ButtonEntity):
    """Write the staged schedule to the inverter (one write)."""

    _attr_name = "Apply schedule"
    _attr_icon = "mdi:content-save-check"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_apply_schedule"

    async def async_press(self) -> None:
        try:
            await self.coordinator.apply_draft()
        except PionApiError as err:
            raise HomeAssistantError(str(err)) from err


class PionReloadButton(PionBaseEntity, ButtonEntity):
    """Discard staged edits and re-read the schedule from the server."""

    _attr_name = "Reload schedule from server"
    _attr_icon = "mdi:reload"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_reload_schedule"

    async def async_press(self) -> None:
        self.coordinator.reload_draft()


class PionAddPeriodButton(PionBaseEntity, ButtonEntity):
    """Append a new blank TOU period to the staged schedule."""

    _attr_name = "Add TOU period"
    _attr_icon = "mdi:plus-box"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_add_period"

    async def async_press(self) -> None:
        self.coordinator.add_period()


class PionDeletePeriodButton(PionPeriodEntity, ButtonEntity):
    """Remove this TOU period from the staged schedule."""

    _attr_name = "Delete period"
    _attr_icon = "mdi:delete"

    def __init__(self, coordinator, entry, index) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_unique_id = f"{entry.entry_id}_period_{index}_delete"

    async def async_press(self) -> None:
        self.coordinator.delete_period(self._index)
