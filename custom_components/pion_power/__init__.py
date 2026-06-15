"""The Pion Power (Hoymiles HAS) integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PionApiError, PionAuthError, PionClient
from .const import (
    CONF_EMAIL,
    CONF_RETRY_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_STATION_CODE,
    DEFAULT_RETRY_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_SET_TOU,
)
from .coordinator import PionCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SWITCH]

PERIOD_SCHEMA = vol.Schema(
    {
        vol.Required("StartTime"): cv.string,
        vol.Required("EndTime"): cv.string,
        vol.Required("ChargeOrDis"): vol.In([1, 2]),
        vol.Optional("SOC", default=100): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("RunPower", default=100): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("GridChargeEn", default=False): cv.boolean,
        vol.Optional("SellGridEn", default=False): cv.boolean,
    }
)
SET_TOU_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("periods"): [PERIOD_SCHEMA],
        vol.Optional("reserved_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pion Power from a config entry."""
    session = async_get_clientsession(hass)
    client = PionClient(session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])

    try:
        await client.login()
    except PionAuthError as err:
        raise ConfigEntryNotReady(f"Authentication failed: {err}") from err
    except Exception as err:  # noqa: BLE001
        raise ConfigEntryNotReady(f"Cannot connect to Pion: {err}") from err

    interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    retry = entry.options.get(CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL)
    coordinator = PionCoordinator(hass, client, entry.data[CONF_STATION_CODE], interval, retry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _async_register_services(hass)
    return True


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SET_TOU):
        return

    async def _set_tou(call: ServiceCall) -> None:
        coordinators = hass.data.get(DOMAIN, {})
        if not coordinators:
            raise HomeAssistantError("Pion Power is not set up")
        entry_id = call.data.get("entry_id")
        if entry_id:
            coordinator = coordinators.get(entry_id)
            if coordinator is None:
                raise HomeAssistantError(f"Unknown entry_id: {entry_id}")
        else:
            coordinator = next(iter(coordinators.values()))
        try:
            await coordinator.client.set_tou_schedule(
                coordinator.station, call.data["periods"], call.data.get("reserved_soc")
            )
        except PionApiError as err:
            raise HomeAssistantError(f"Failed to set TOU schedule: {err}") from err
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_SET_TOU, _set_tou, schema=SET_TOU_SCHEMA)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_SET_TOU)
    return unload_ok
