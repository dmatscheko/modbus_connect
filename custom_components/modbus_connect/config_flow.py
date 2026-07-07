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
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

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
from .loader import async_load_all, async_load_device
from .models import DeviceDef
from .schema import DeviceSchemaError


def _device_schema(
    devices: dict[str, DeviceDef], defaults: dict[str, Any] | None = None
) -> vol.Schema:
    defaults = defaults or {}
    choices = {
        name: f"{d.manufacturer} {d.model}"
        for name, d in sorted(
            devices.items(), key=lambda kv: (kv[1].manufacturer, kv[1].model)
        )
    }
    default_file = defaults.get(CONF_FILENAME)
    return vol.Schema(
        {
            vol.Required(
                CONF_FILENAME,
                default=default_file if default_file in choices else vol.UNDEFINED,
            ): vol.In(choices),
            vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
        }
    )


def _connection_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required(
                CONF_SLAVE_ID, default=defaults.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
            ): vol.All(
                NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=255, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Coerce(int),
            ),
            vol.Optional(CONF_PREFIX, default=defaults.get(CONF_PREFIX, "")): str,
        }
    )


def _unique_id(connection: dict[str, Any]) -> str:
    return f"{connection[CONF_HOST]}:{connection[CONF_PORT]}:{connection[CONF_SLAVE_ID]}"


class ModbusConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Two steps: device file + name, then the gateway connection."""

    VERSION = 1

    def __init__(self) -> None:
        self._filename: str = ""
        self._name: str = ""
        self._device: DeviceDef | None = None

    @property
    def _title(self) -> str:
        assert self._device is not None
        return self._name or f"{self._device.manufacturer} {self._device.model}"

    def _store_device_choice(
        self, devices: dict[str, DeviceDef], user_input: dict[str, Any]
    ) -> None:
        self._filename = user_input[CONF_FILENAME]
        self._name = (user_input.get(CONF_NAME) or "").strip()
        self._device = devices[self._filename]

    def _connection_defaults(self) -> dict[str, Any]:
        """Prefill for a fresh connection form from the chosen device file."""
        assert self._device is not None
        return {
            CONF_SLAVE_ID: self._device.modbus_id or DEFAULT_SLAVE_ID,
            CONF_PREFIX: self._device.prefix or self._title,
        }

    def _entry_data(self, connection: dict[str, Any]) -> dict[str, Any]:
        return {
            CONF_FILENAME: self._filename,
            CONF_NAME: self._name,
            **connection,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        devices = await async_load_all(self.hass)
        if not devices:
            return self.async_abort(reason="no_device_files")

        if user_input is not None:
            self._store_device_choice(devices, user_input)
            return await self.async_step_connection()

        return self.async_show_form(step_id="user", data_schema=_device_schema(devices))

    async def async_step_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(_unique_id(user_input))
            self._abort_if_unique_id_configured()
            if await async_probe(user_input[CONF_HOST], user_input[CONF_PORT]):
                return self.async_create_entry(
                    title=self._title, data=self._entry_data(user_input)
                )
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="connection",
            data_schema=_connection_schema(user_input or self._connection_defaults()),
            description_placeholders={"device": self._title},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change device file, name, and/or connection of an existing entry."""
        entry = self._get_reconfigure_entry()
        devices = await async_load_all(self.hass)
        if not devices:
            return self.async_abort(reason="no_device_files")

        if user_input is not None:
            self._store_device_choice(devices, user_input)
            return await self.async_step_reconfigure_connection()

        defaults = {
            CONF_FILENAME: entry.data.get(CONF_FILENAME),
            # Old entries stored the device name in CONF_PREFIX
            CONF_NAME: entry.data.get(CONF_NAME) or entry.data.get(CONF_PREFIX) or "",
        }
        return self.async_show_form(
            step_id="reconfigure", data_schema=_device_schema(devices, defaults)
        )

    async def async_step_reconfigure_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(_unique_id(user_input))
            if self.unique_id != entry.unique_id:
                self._abort_if_unique_id_configured()
            if await async_probe(user_input[CONF_HOST], user_input[CONF_PORT]):
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=self.unique_id,
                    title=self._title,
                    data=self._entry_data(user_input),
                )
            errors["base"] = "cannot_connect"
        defaults = user_input or {
            **dict(entry.data),
            **(
                {} if entry.data.get(CONF_PREFIX) else
                {CONF_PREFIX: self._connection_defaults()[CONF_PREFIX]}
            ),
        }
        return self.async_show_form(
            step_id="reconfigure_connection",
            data_schema=_connection_schema(defaults),
            description_placeholders={"device": self._title},
            errors=errors,
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
        current = self.config_entry.options.get(OPTION_SCAN_INTERVAL)
        if current is None:
            current = await self._device_default() or DEFAULT_SCAN_INTERVAL
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

    async def _device_default(self) -> int | None:
        """The device file's scan_interval, if the file still loads."""
        try:
            device = await async_load_device(
                self.hass, self.config_entry.data[CONF_FILENAME]
            )
        except DeviceSchemaError:
            return None
        return device.scan_interval
