"""Config and options flow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback

from .client import async_probe
from .const import (
    CONF_FILENAME,
    CONF_PREFIX,
    CONF_SLAVE_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DOMAIN,
    OPTION_SCAN_INTERVAL,
)
from .loader import async_load_all
from .models import DeviceDef


def _connection_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required(
                CONF_SLAVE_ID, default=defaults.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Optional(CONF_PREFIX, default=defaults.get(CONF_PREFIX, "")): str,
        }
    )


def _device_schema(devices: dict[str, DeviceDef], default: str | None = None) -> vol.Schema:
    choices = {
        name: f"{d.manufacturer} {d.model}"
        for name, d in sorted(
            devices.items(), key=lambda kv: (kv[1].manufacturer, kv[1].model)
        )
    }
    key = vol.Required(CONF_FILENAME, default=default if default in choices else vol.UNDEFINED)
    return vol.Schema({key: vol.In(choices)})


def _unique_id(connection: dict[str, Any]) -> str:
    return f"{connection[CONF_HOST]}:{connection[CONF_PORT]}:{connection[CONF_SLAVE_ID]}"


class ModbusConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Two steps: gateway connection, then device file."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(_unique_id(user_input))
            self._abort_if_unique_id_configured()
            if await async_probe(user_input[CONF_HOST], user_input[CONF_PORT]):
                self._connection = user_input
                return await self.async_step_device()
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(user_input),
            errors=errors,
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        devices = await async_load_all(self.hass)
        if not devices:
            return self.async_abort(reason="no_device_files")

        if user_input is not None:
            filename = user_input[CONF_FILENAME]
            device = devices[filename]
            title = (
                self._connection.get(CONF_PREFIX)
                or f"{device.manufacturer} {device.model}"
            )
            return self.async_create_entry(
                title=title, data={**self._connection, CONF_FILENAME: filename}
            )

        return self.async_show_form(step_id="device", data_schema=_device_schema(devices))

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change gateway connection and/or device file of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(_unique_id(user_input))
            if self.unique_id != entry.unique_id:
                self._abort_if_unique_id_configured()
            if await async_probe(user_input[CONF_HOST], user_input[CONF_PORT]):
                self._connection = user_input
                return await self.async_step_reconfigure_device()
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(user_input or dict(entry.data)),
            errors=errors,
        )

    async def async_step_reconfigure_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        devices = await async_load_all(self.hass)
        if not devices:
            return self.async_abort(reason="no_device_files")

        if user_input is not None:
            filename = user_input[CONF_FILENAME]
            device = devices[filename]
            title = (
                self._connection.get(CONF_PREFIX)
                or f"{device.manufacturer} {device.model}"
            )
            return self.async_update_reload_and_abort(
                entry,
                unique_id=self.unique_id,
                title=title,
                data={**self._connection, CONF_FILENAME: filename},
            )

        return self.async_show_form(
            step_id="reconfigure_device",
            data_schema=_device_schema(devices, default=entry.data.get(CONF_FILENAME)),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ModbusConnectOptionsFlow:
        return ModbusConnectOptionsFlow()


class ModbusConnectOptionsFlow(OptionsFlow):
    """Update interval override."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(OPTION_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(OPTION_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=86400)
                    )
                }
            ),
        )
