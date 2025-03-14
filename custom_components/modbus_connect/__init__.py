"""The Modbus Connect sensor integration."""

import logging

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_SLAVE_ID,
    DOMAIN,
    OPTIONS_REFRESH_DEFAULT,
    OPTIONS_REFRESH,
    PLATFORMS,
)
from .entity_management.base import MirroredSensorEntityDescription
from .coordinator import ModbusCoordinator
from .helpers import get_gateway_key
from .tcp_client import AsyncModbusTcpClientGateway

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Load the saved entities."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    gateway_key: str = get_gateway_key(entry=entry)

    device_registry: dr.DeviceRegistry = dr.async_get(hass)

    device: dr.DeviceEntry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"ModbusGateway-{gateway_key}")},
        name=f"Modbus Gateway ({gateway_key})",
        configuration_url=f"http://{entry.data[CONF_HOST]}/",
    )

    if gateway_key not in hass.data[DOMAIN]:
        client: AsyncModbusTcpClientGateway = AsyncModbusTcpClientGateway.async_get_client_connection(
            host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]
        )
        if client is not None:
            hass.data[DOMAIN][gateway_key] = ModbusCoordinator(
                hass=hass,
                gateway_device=device,
                client=client,
                gateway=gateway_key,
                update_interval=entry.options.get(OPTIONS_REFRESH, OPTIONS_REFRESH_DEFAULT),
            )
        else:
            raise ConfigEntryNotReady(f"Unable to connect to {gateway_key}, slave: {entry.data[CONF_SLAVE_ID]}")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Register the update listener for dynamic option changes
    entry.async_on_unload(entry.add_update_listener(update_listener))
    _LOGGER.debug("Update listener registered for entry %s", entry.entry_id)
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Update listener triggered for entry %s with options: %s", entry.entry_id, entry.options)

    # # This worked but is not good because "_mirror" could be a legitimate key ending:
    # if entry.options["mirror_non_sensors"]:
    #     # Reload the integration to apply the changes
    #     await hass.config_entries.async_reload(entry.entry_id)
    # else:
    #     # Clean up mirrored entities if the option is disabled
    #     entity_reg = er.async_get(hass)
    #     entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)
    #     mirrored_entities = [entity for entity in entities if entity.unique_id.endswith("_mirror")]
    #     for entity in mirrored_entities:
    #         entity_reg.async_remove(entity.entity_id)

    # coordinator: ModbusCoordinator = hass.data[DOMAIN][get_gateway_key(entry)]
    # coordinator._recompute_read_plan = True

    coordinator: ModbusCoordinator = hass.data[DOMAIN][get_gateway_key(entry)]

    if not entry.options["mirror_non_sensors"]:
        # Clean up mirrored entities if the option is disabled
        entity_reg = er.async_get(hass)
        entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)
        for entity in entities:
            entity_reg.async_remove(entity.entity_id)

    coordinator._recompute_read_plan = True
    # Reload the integration to apply the changes
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Async unload entry triggered for entry %s with options: %s", entry.entry_id, entry.options)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
