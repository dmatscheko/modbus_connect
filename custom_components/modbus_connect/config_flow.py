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
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .client import (
    DEFAULT_BAUDRATE,
    async_probe,
    async_probe_device,
    async_probe_serial,
    async_probe_serial_device,
)
from .const import (
    BAUDRATE_OPTIONS,
    BYTESIZE_OPTIONS,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_FILENAME,
    CONF_FRAMER,
    CONF_PARITY,
    CONF_PREFIX,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DOMAIN,
    FRAMER_OPTIONS,
    FRAMER_SOCKET,
    OPTION_ENABLED_GROUPS,
    OPTION_MIN_SCAN_INTERVAL,
    OPTION_SHOW_ALL,
    PARITY_OPTIONS,
    STOPBITS_OPTIONS,
)
from .coordinator import resolve_scan_intervals
from .loader import async_load_all, async_load_device
from .models import DeviceDef, Span
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
                CONF_FRAMER, default=defaults.get(CONF_FRAMER, FRAMER_SOCKET)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=FRAMER_OPTIONS,
                    translation_key="framer",
                    mode=SelectSelectorMode.DROPDOWN,
                )
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


def _serial_schema(defaults: dict[str, Any], ports: list[str]) -> vol.Schema:
    current = defaults.get(CONF_SERIAL_PORT)
    if current and current not in ports:
        ports = [current, *ports]  # keep a configured-but-unplugged port pickable
    return vol.Schema(
        {
            vol.Required(
                CONF_SERIAL_PORT, default=current if current else vol.UNDEFINED
            ): SelectSelector(
                SelectSelectorConfig(
                    options=ports, custom_value=True, mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(
                CONF_BAUDRATE,
                default=str(defaults.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)),
            ): vol.All(
                SelectSelector(
                    SelectSelectorConfig(
                        options=BAUDRATE_OPTIONS,
                        custom_value=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Coerce(int),
                vol.Range(min=50, max=4_000_000),
            ),
            vol.Required(
                CONF_BYTESIZE, default=str(defaults.get(CONF_BYTESIZE, 8))
            ): vol.All(
                SelectSelector(
                    SelectSelectorConfig(
                        options=BYTESIZE_OPTIONS, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Coerce(int),
            ),
            vol.Required(
                CONF_PARITY, default=defaults.get(CONF_PARITY, "N")
            ): SelectSelector(
                SelectSelectorConfig(
                    options=PARITY_OPTIONS,
                    translation_key="parity",
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_STOPBITS, default=str(defaults.get(CONF_STOPBITS, 1))
            ): vol.All(
                SelectSelector(
                    SelectSelectorConfig(
                        options=STOPBITS_OPTIONS, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Coerce(int),
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


def _list_serial_ports() -> list[str]:
    """Detected serial devices for the port dropdown (custom paths stay typable).

    Runs in the executor: pyserial enumerates the system's ports synchronously.
    """
    from serial.tools import list_ports

    return sorted(port.device for port in list_ports.comports())


def _unique_id(connection: dict[str, Any]) -> str:
    # Hostnames are case-insensitive; normalize so "GW" and "gw" don't create
    # two entries for the same device.
    host = str(connection[CONF_HOST]).strip().lower()
    return f"{host}:{connection[CONF_PORT]}:{connection[CONF_SLAVE_ID]}"


def _serial_unique_id(connection: dict[str, Any]) -> str:
    # Device paths are case-sensitive on Linux; only whitespace is normalized
    # (which async_step_serial already stripped).
    return f"{connection[CONF_SERIAL_PORT]}:{connection[CONF_SLAVE_ID]}"


def _probe_span(device: DeviceDef) -> Span | None:
    """The smallest register span the device file polls — the cheapest real
    read that proves a device with the entered Modbus ID answers."""
    readers = [e for e in device.entities if e.polls]
    if not readers:
        return None
    return min(readers, key=lambda e: (e.count, e.address)).span


class ModbusConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Two steps: device file + name, then the gateway connection."""

    VERSION = 1

    def __init__(self) -> None:
        self._filename: str = ""
        self._name: str = ""
        self._device: DeviceDef | None = None
        self._devices: dict[str, DeviceDef] | None = None
        self._load_errors: dict[str, str] = {}

    async def _load_devices(self) -> dict[str, DeviceDef]:
        """Load device definitions once and reuse them across this flow's steps."""
        if self._devices is None:
            self._devices, self._load_errors = await async_load_all(self.hass)
        return self._devices

    @property
    def _failed_note(self) -> str:
        """Markdown note listing skipped device files; "" when all loaded."""
        if not self._load_errors:
            return ""
        lines = "\n".join(f"- {error}" for error in self._load_errors.values())
        return f"\n\n**Skipped invalid device files:**\n{lines}"

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

    async def _validate_connection(self, connection: dict[str, Any]) -> str | None:
        """Probe the gateway and the device itself; an error key, or None if OK.

        Reads one small span from the chosen device file, so a wrong Modbus ID
        fails here with a pointed message instead of setting up an entry whose
        entities are all unavailable. A file that never polls (only buttons /
        write-only registers) falls back to the plain TCP probe.
        """
        assert self._device is not None
        span = _probe_span(self._device)
        if span is None:
            ok = await async_probe(connection[CONF_HOST], connection[CONF_PORT])
            return None if ok else "cannot_connect"
        return await async_probe_device(
            connection[CONF_HOST],
            connection[CONF_PORT],
            connection[CONF_SLAVE_ID],
            span,
            framer=connection.get(CONF_FRAMER, FRAMER_SOCKET),
        )

    async def _validate_serial(self, connection: dict[str, Any]) -> str | None:
        """Serial twin of :meth:`_validate_connection`."""
        assert self._device is not None
        span = _probe_span(self._device)
        line = {
            "baudrate": connection[CONF_BAUDRATE],
            "bytesize": connection[CONF_BYTESIZE],
            "parity": connection[CONF_PARITY],
            "stopbits": connection[CONF_STOPBITS],
        }
        if span is None:
            ok = await async_probe_serial(connection[CONF_SERIAL_PORT], **line)
            return None if ok else "cannot_connect"
        return await async_probe_serial_device(
            connection[CONF_SERIAL_PORT], connection[CONF_SLAVE_ID], span, **line
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        devices = await self._load_devices()
        if not devices:
            return self.async_abort(reason="no_device_files")

        if user_input is not None:
            self._store_device_choice(devices, user_input)
            return await self.async_step_connection_type()

        return self.async_show_form(
            step_id="user",
            data_schema=_device_schema(devices),
            description_placeholders={"failed": self._failed_note},
        )

    async def async_step_connection_type(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """How the device is reached: network gateway or local serial port."""
        return self.async_show_menu(
            step_id="connection_type", menu_options=["connection", "serial"]
        )

    async def async_step_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(_unique_id(user_input))
            self._abort_if_unique_id_configured()
            error = await self._validate_connection(user_input)
            if error is None:
                return self.async_create_entry(
                    title=self._title, data=self._entry_data(user_input)
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="connection",
            data_schema=_connection_schema(user_input or self._connection_defaults()),
            description_placeholders={"device": self._title},
            errors=errors,
        )

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_SERIAL_PORT] = user_input[CONF_SERIAL_PORT].strip()
            await self.async_set_unique_id(_serial_unique_id(user_input))
            self._abort_if_unique_id_configured()
            error = await self._validate_serial(user_input)
            if error is None:
                return self.async_create_entry(
                    title=self._title, data=self._entry_data(user_input)
                )
            errors["base"] = error
        ports = await self.hass.async_add_executor_job(_list_serial_ports)
        return self.async_show_form(
            step_id="serial",
            data_schema=_serial_schema(user_input or self._connection_defaults(), ports),
            description_placeholders={"device": self._title},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change device file, name, and/or connection of an existing entry."""
        entry = self._get_reconfigure_entry()
        devices = await self._load_devices()
        if not devices:
            return self.async_abort(reason="no_device_files")

        if user_input is not None:
            self._store_device_choice(devices, user_input)
            return await self.async_step_reconfigure_connection_type()

        defaults = {
            CONF_FILENAME: entry.data.get(CONF_FILENAME),
            # Old entries stored the device name in CONF_PREFIX
            CONF_NAME: entry.data.get(CONF_NAME) or entry.data.get(CONF_PREFIX) or "",
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_device_schema(devices, defaults),
            description_placeholders={"failed": self._failed_note},
        )

    async def async_step_reconfigure_connection_type(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="reconfigure_connection_type",
            menu_options=["reconfigure_connection", "reconfigure_serial"],
        )

    def _finish_reconfigure(
        self, entry: ConfigEntry, connection: dict[str, Any]
    ) -> ConfigFlowResult:
        kwargs: dict[str, Any] = {}
        if self._filename != entry.data.get(CONF_FILENAME):
            # A different device file has different groups; a stale
            # selection would hide every tagged entity, and the show-all
            # bypass belonged to the old file's groups just the same.
            kwargs["options"] = {
                k: v
                for k, v in entry.options.items()
                if k not in (OPTION_ENABLED_GROUPS, OPTION_SHOW_ALL)
            }
        return self.async_update_reload_and_abort(
            entry,
            unique_id=self.unique_id,
            title=self._title,
            data=self._entry_data(connection),
            **kwargs,
        )

    async def async_step_reconfigure_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(_unique_id(user_input))
            if self.unique_id != entry.unique_id:
                self._abort_if_unique_id_configured()
            error = await self._validate_connection(user_input)
            if error is None:
                return self._finish_reconfigure(entry, user_input)
            errors["base"] = error
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

    async def async_step_reconfigure_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_SERIAL_PORT] = user_input[CONF_SERIAL_PORT].strip()
            await self.async_set_unique_id(_serial_unique_id(user_input))
            if self.unique_id != entry.unique_id:
                self._abort_if_unique_id_configured()
            error = await self._validate_serial(user_input)
            if error is None:
                return self._finish_reconfigure(entry, user_input)
            errors["base"] = error
        ports = await self.hass.async_add_executor_job(_list_serial_ports)
        defaults = user_input or {
            **dict(entry.data),
            **(
                {} if entry.data.get(CONF_PREFIX) else
                {CONF_PREFIX: self._connection_defaults()[CONF_PREFIX]}
            ),
        }
        return self.async_show_form(
            step_id="reconfigure_serial",
            data_schema=_serial_schema(defaults, ports),
            description_placeholders={"device": self._title},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ModbusConnectOptionsFlow:
        return ModbusConnectOptionsFlow()


class ModbusConnectOptionsFlow(OptionsFlow):
    """Set the minimum poll interval (a floor the device file / entities sit above)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            # Merge: async_create_entry replaces the whole options dict, and
            # other keys (the group selection) must survive this form.
            return self.async_create_entry(
                data={**self.config_entry.options, **user_input}
            )
        current = self.config_entry.options.get(OPTION_MIN_SCAN_INTERVAL)
        if current is None:
            current = await self._device_default() or DEFAULT_SCAN_INTERVAL
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(OPTION_MIN_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=86400)
                    )
                }
            ),
        )

    async def _device_default(self) -> int | None:
        """The device's current poll-interval floor, if the file still loads.

        Prefilling with this makes accepting the form without changes a no-op.
        """
        try:
            device = await async_load_device(
                self.hass, self.config_entry.data[CONF_FILENAME]
            )
        except DeviceSchemaError:
            return None
        return resolve_scan_intervals(device)[1]
