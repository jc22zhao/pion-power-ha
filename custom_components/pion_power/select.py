"""Select platform: charge/discharge mode of each TOU period (edits the draft)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import PionPeriodEntity, setup_period_entities

# ChargeOrDis: 0=auto (hold/charge toward SOC, discharge above it), 1=charge, 2=discharge.
MODE_TO_CODE = {"Auto": 0, "Charge": 1, "Discharge": 2}
CODE_TO_MODE = {v: k for k, v in MODE_TO_CODE.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]

    def _factory(coord, ent, index):
        return [PionPeriodModeSelect(coord, ent, index)]

    setup_period_entities(coordinator, entry, async_add_entities, _factory)


class PionPeriodModeSelect(PionPeriodEntity, SelectEntity):
    """Charge/discharge mode of one TOU period."""

    _attr_name = "Mode"
    _attr_icon = "mdi:battery-charging-medium"
    _attr_options = list(MODE_TO_CODE)

    def __init__(self, coordinator, entry, index) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_unique_id = f"{entry.entry_id}_period_{index}_mode"

    @property
    def current_option(self) -> str | None:
        period = self._period
        if period is None:
            return None
        return CODE_TO_MODE.get(int(period.get("ChargeOrDis") or 0), "Auto")

    async def async_select_option(self, option: str) -> None:
        self.coordinator.edit_period(self._index, "ChargeOrDis", MODE_TO_CODE.get(option, 0))
