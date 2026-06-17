"""The Pion Power (Hoymiles HAS) integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .api import PionApiError, PionAuthError, PionClient
from .const import (
    CONF_ALLOW_WRITE,
    CONF_EMAIL,
    CONF_RETRY_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_STATION_CODE,
    DEFAULT_ALLOW_WRITE,
    DEFAULT_RETRY_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_SET_TOU,
    SERVICE_SET_TOU_TEMPLATE,
)
from .coordinator import PionCoordinator
from .schedule import build_stra_day_periods, workmode_charge_periods

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.TIME,
    Platform.BUTTON,
]

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

# --- General template editing (handles any schedule shape) ---
# A template period: RunPower/SOC are percentages (0-100); ChargeOrDis 0=auto
# (hold/charge toward SOC, discharge above it), 1=charge, 2=discharge.
TPL_PERIOD_SCHEMA = vol.Schema(
    {
        vol.Required("StartTime"): cv.string,
        vol.Required("EndTime"): cv.string,
        vol.Optional("SOC", default=100): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("RunPower", default=100): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("ChargeOrDis", default=0): vol.In([0, 1, 2]),
        vol.Optional("GridChargeEn", default=False): cv.boolean,
        vol.Optional("SellGridEn", default=False): cv.boolean,
    }
)
# A rule-group: an optional date range + weekday set + its periods. Omitting the
# date range means all year; omitting weeks means every day.
TPL_GROUP_SCHEMA = vol.Schema(
    {
        vol.Optional("start_month", default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=12)),
        vol.Optional("start_day", default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=31)),
        vol.Optional("end_month", default=12): vol.All(vol.Coerce(int), vol.Range(min=1, max=12)),
        vol.Optional("end_day", default=31): vol.All(vol.Coerce(int), vol.Range(min=1, max=31)),
        vol.Optional("weeks", default=[0, 1, 2, 3, 4, 5, 6]): [vol.In([0, 1, 2, 3, 4, 5, 6])],
        vol.Required("periods"): [TPL_PERIOD_SCHEMA],
    }
)
SET_TOU_TEMPLATE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Optional("template_id"): cv.string,
        vol.Optional("template_name"): cv.string,
        vol.Required("groups"): vol.All([TPL_GROUP_SCHEMA], vol.Length(min=1)),
        vol.Optional("special_days"): list,
        vol.Optional("reserved_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("activate", default=True): cv.boolean,
    }
)




async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pion Power from a config entry."""
    session = async_get_clientsession(hass)
    client = PionClient(session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])

    try:
        await client.login()
    except PionAuthError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except Exception as err:  # noqa: BLE001
        raise ConfigEntryNotReady(f"Cannot connect to Pion: {err}") from err

    station = entry.data[CONF_STATION_CODE]
    device_code = None
    try:
        devices = await client.get_devices(station)
        device_code = next(
            (d.get("DeviceCode") for d in devices if str(d.get("DeviceType")) == "102"), None
        )
    except Exception:  # noqa: BLE001
        device_code = None

    interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    retry = entry.options.get(CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL)
    allow_write = entry.options.get(CONF_ALLOW_WRITE, DEFAULT_ALLOW_WRITE)
    coordinator = PionCoordinator(
        hass, client, station, interval, retry, device_code, allow_write
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _async_register_services(hass)
    return True


def _resolve_coordinator(hass: HomeAssistant, call: ServiceCall):
    coordinators = hass.data.get(DOMAIN, {})
    if not coordinators:
        raise HomeAssistantError("Pion Power is not set up")
    entry_id = call.data.get("entry_id")
    if entry_id:
        coordinator = coordinators.get(entry_id)
        if coordinator is None:
            raise HomeAssistantError(f"Unknown entry_id: {entry_id}")
        return coordinator
    return next(iter(coordinators.values()))


def _require_write(coordinator) -> None:
    if not coordinator.allow_write:
        raise HomeAssistantError(
            "Schedule writing is disabled. Enable 'Allow schedule writes' in the "
            "Pion Power integration options once your system is healthy."
        )


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SET_TOU):
        return

    async def _set_tou(call: ServiceCall) -> None:
        coordinator = _resolve_coordinator(hass, call)
        _require_write(coordinator)
        try:
            await coordinator.client.set_tou_schedule(
                coordinator.station, call.data["periods"], call.data.get("reserved_soc")
            )
        except PionApiError as err:
            raise HomeAssistantError(f"Failed to set TOU schedule: {err}") from err
        await coordinator.async_request_refresh()

    async def _set_tou_template(call: ServiceCall) -> None:
        coordinator = _resolve_coordinator(hass, call)
        _require_write(coordinator)
        client = coordinator.client
        template_id = call.data.get("template_id")
        try:
            # Default to the station's active template; preserve its metadata so
            # we only replace the schedule, not name/description/geo.
            if not template_id:
                tpls = await client.get_station_tou_templates(coordinator.station)
                active = next(
                    (t for t in (tpls.get("StationTous") or []) if t.get("StraEn")), None
                )
                if active:
                    template_id = active.get("TemplateId")
            base = {}
            if template_id:
                base = await client.get_tou_template_detail(template_id) or {}
            payload = {k: v for k, v in base.items() if not k.startswith("_")}
            payload["CompanyCode"] = base.get("CompanyCode") or "PionPower"
            if template_id:
                payload["TemplateId"] = template_id
            if call.data.get("template_name"):
                payload["TemplateName"] = call.data["template_name"]
            payload.setdefault("TemplateName", "Home Assistant")
            payload["StraDayPeriods"] = build_stra_day_periods(call.data["groups"])
            payload["StraSpecialDayInfos"] = call.data.get(
                "special_days", payload.get("StraSpecialDayInfos") or []
            )
            result = await client.add_or_update_template(payload)
            new_id = result.get("TemplateId") or template_id
            if call.data.get("activate", True) and new_id:
                await client.choose_tou_template(coordinator.station, new_id)
            # The inverter executes the workmode, not the template — push the
            # grid-charge windows so the schedule actually takes effect.
            all_periods = [p for g in call.data["groups"] for p in g["periods"]]
            await client.set_tou_schedule(
                coordinator.station,
                workmode_charge_periods(all_periods),
                reserved_soc=call.data.get("reserved_soc"),
            )
        except PionApiError as err:
            raise HomeAssistantError(f"Failed to set TOU template: {err}") from err
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_SET_TOU, _set_tou, schema=SET_TOU_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_SET_TOU_TEMPLATE, _set_tou_template, schema=SET_TOU_TEMPLATE_SCHEMA
    )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Allow removing a device from the UI once it has no entities left.

    The pre-2.0 period editor created 'TOU Period N' sub-devices; 2.0+ replaced
    them with 'Charge Window N'. After their old entities are deleted those
    period devices are orphaned. Devices the integration still provides keep
    their entities (recreated on reload), so only genuinely empty/stale devices
    can be removed this way."""
    ent_reg = er.async_get(hass)
    return not er.async_entries_for_device(
        ent_reg, device_entry.id, include_disabled_entities=True
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_SET_TOU)
            hass.services.async_remove(DOMAIN, SERVICE_SET_TOU_TEMPLATE)
    return unload_ok
