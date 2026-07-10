"""Modbus Connect: YAML-defined Modbus devices with block-optimized polling."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr

from .client import ModbusBlockClient
from .const import CONF_FILENAME, CONF_FRAMER, FRAMER_SOCKET, PLATFORMS
from .coordinator import ModbusConnectConfigEntry, ModbusConnectCoordinator
from .loader import async_load_device
from .schema import DeviceSchemaError


async def async_setup_entry(hass: HomeAssistant, entry: ModbusConnectConfigEntry) -> bool:
    """Set up one device (gateway + slave id + device YAML)."""
    try:
        device = await async_load_device(hass, entry.data[CONF_FILENAME])
    except DeviceSchemaError as err:
        raise ConfigEntryError(str(err)) from err

    client = ModbusBlockClient.acquire(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.entry_id,
        framer=entry.data.get(CONF_FRAMER, FRAMER_SOCKET),
    )
    coordinator = ModbusConnectCoordinator(hass, entry, client, device)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        client.release(entry.entry_id)
        raise

    # Fill firmware/hardware/serial from the first read before entities (and the
    # device registry entry) are created.
    coordinator.apply_device_info()
    # Register both devices up front: the meta device (group toggles,
    # diagnostics) must exist even when every entity of the device happens to
    # be group-hidden, and the main device must exist for its via_device link.
    # Cross-linking the pair puts a "Connected via" jump on both info cards.
    registry = dr.async_get(hass)
    main_device = registry.async_get_or_create(
        config_entry_id=entry.entry_id, **coordinator.device_info
    )
    meta_device = registry.async_get_or_create(
        config_entry_id=entry.entry_id, **coordinator.meta_device_info
    )
    registry.async_update_device(main_device.id, via_device_id=meta_device.id)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ModbusConnectConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ModbusConnectConfigEntry) -> bool:
    """Unload a device and drop its gateway reference."""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        entry.runtime_data.client.release(entry.entry_id)
    return ok
