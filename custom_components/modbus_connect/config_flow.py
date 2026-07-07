"""Config and options flow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback

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

CONNECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        ),
        vol.Optional(CONF_PREFIX, default=""): str,
    }
)


class ModbusConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Two steps: gateway connection, then device file."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                f":{user_input[CONF_SLAVE_ID]}"
            )
            self._abort_if_unique_id_configured()
            self._connection = user_input
            return await self.async_step_device()
        return self.async_show_form(step_id="user", data_schema=CONNECTION_SCHEMA)

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

        choices = {
            name: f"{d.manufacturer} {d.model}"
            for name, d in sorted(
                devices.items(), key=lambda kv: (kv[1].manufacturer, kv[1].model)
            )
        }
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({vol.Required(CONF_FILENAME): vol.In(choices)}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> ModbusConnectOptionsFlow:
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
