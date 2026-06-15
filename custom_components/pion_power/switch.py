"""Switch platform: manually hand the single session to the mobile app."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import PionBaseEntity, PionPeriodEntity, setup_period_entities

# Per-period boolean fields: (draft key, name, icon). Number-prefixed for order.
PERIOD_SWITCHES = [
    ("GridChargeEn", "6 Grid Charge", "mdi:transmission-tower-import"),
    ("SellGridEn", "7 Sell to Grid", "mdi:transmission-tower-export"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PionCloudConnectionSwitch(coordinator, entry)])

    def _factory(coord, ent, index):
        return [
            PionPeriodSwitch(coord, ent, index, key, name, icon)
            for key, name, icon in PERIOD_SWITCHES
        ]

    setup_period_entities(coordinator, entry, async_add_entities, _factory)


class PionCloudConnectionSwitch(PionBaseEntity, SwitchEntity):
    """ON = HA stays connected (polls/controls the cloud).
    OFF = HA releases the session so you can use the Pion mobile app uninterrupted."""

    _attr_name = "Cloud Connection"
    _attr_icon = "mdi:cloud-sync"
    _attr_entity_category = None

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_cloud_connection"

    @property
    def is_on(self) -> bool:
        return not self.coordinator.paused

    @property
    def available(self) -> bool:
        return True  # stays controllable even while paused / data is stale

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.resume()
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.pause()
        self.async_write_ha_state()


class PionPeriodSwitch(PionPeriodEntity, SwitchEntity):
    """A boolean field of one TOU period (edits the draft; commit via Apply)."""

    def __init__(self, coordinator, entry, index, key, name, icon) -> None:
        super().__init__(coordinator, entry, index)
        self._field = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_period_{index}_{key}"

    @property
    def is_on(self) -> bool | None:
        period = self._period
        return None if period is None else bool(period.get(self._field))

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.edit_period(self._index, self._field, True)

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.edit_period(self._index, self._field, False)
