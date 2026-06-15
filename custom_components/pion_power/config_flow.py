"""Config flow for Pion Power (Hoymiles HAS)."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PionAuthError, PionClient
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
)


class PionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI configuration flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._creds: dict[str, Any] = {}
        self._stations: list[dict] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = PionClient(session, user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            try:
                await client.login()
                self._stations = await client.get_stations()
            except PionAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                self._creds = user_input
                if not self._stations:
                    errors["base"] = "no_stations"
                else:
                    return await self.async_step_station()
        schema = vol.Schema(
            {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def _validate_login(self, email: str, password: str) -> str | None:
        """Try to log in. Returns an error key, or None on success."""
        session = async_get_clientsession(self.hass)
        client = PionClient(session, email, password)
        try:
            await client.login()
        except PionAuthError:
            return "invalid_auth"
        except Exception:  # noqa: BLE001
            return "cannot_connect"
        return None

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update the email/password on the existing entry (keeps station + entities)."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._validate_login(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=entry.data.get(CONF_EMAIL)): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Triggered when the API rejects our login (e.g. password changed)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            email = entry.data[CONF_EMAIL]
            error = await self._validate_login(email, user_input[CONF_PASSWORD])
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={"email": self._get_reauth_entry().data.get(CONF_EMAIL)},
        )

    async def async_step_station(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            code = user_input[CONF_STATION_CODE]
            await self.async_set_unique_id(code)
            self._abort_if_unique_id_configured()
            name = next(
                (s.get("StationName") for s in self._stations if s.get("StationCode") == code),
                code,
            )
            return self.async_create_entry(
                title=name, data={**self._creds, CONF_STATION_CODE: code}
            )
        options = {
            s.get("StationCode"): f"{s.get('StationName')} ({s.get('StationCode')})"
            for s in self._stations
            if s.get("StationCode")
        }
        schema = vol.Schema({vol.Required(CONF_STATION_CODE): vol.In(options)})
        return self.async_show_form(step_id="station", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PionOptionsFlow()


class PionOptionsFlow(OptionsFlow):
    """Options: polling interval, app-coexistence retry interval, write enable."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(int, vol.Range(min=10, max=3600)),
                vol.Required(
                    CONF_RETRY_INTERVAL,
                    default=opts.get(CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL),
                ): vol.All(int, vol.Range(min=60, max=7200)),
                vol.Required(
                    CONF_ALLOW_WRITE,
                    default=opts.get(CONF_ALLOW_WRITE, DEFAULT_ALLOW_WRITE),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
