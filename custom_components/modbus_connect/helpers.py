"""Helper functions for Modbus Connect integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILENAME, CONF_HOST, CONF_PORT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_PREFIX, CONF_SLAVE_ID, DOMAIN, OPTIONS_MIRROR_NON_SENSORS, OPTIONS_MIRROR_NON_SENSORS_DEFAULT

from .coordinator import ModbusContext, ModbusCoordinator, ModbusCoordinatorEntity
from .entity_management.const import ControlType, ModbusDataType
from .entity_management.device_loader import create_device_info
from .entity_management.modbus_device_info import ModbusDeviceInfo
from .entity_management.base import (
    MirroredSensorEntityDescription,
    ModbusSelectEntityDescription,
    ModbusSwitchEntityDescription,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)


def get_gateway_key(entry: ConfigEntry, with_slave: bool = True) -> str:
    """Get the gateway key for the coordinator"""
    if with_slave:
        return f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}:{entry.data[CONF_SLAVE_ID]}"

    return f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"


def create_mirrored_sensor_description(original_desc):
    """Generate a mirrored sensor description from a non-sensor entity."""
    # Determine conv_map based on control type
    conv_map = getattr(original_desc, "conv_map", None)
    if getattr(original_desc, "control_type", None) == ControlType.SELECT:
        if isinstance(original_desc, ModbusSelectEntityDescription):
            conv_map = getattr(original_desc, "select_options", None)
    elif (
        getattr(original_desc, "control_type", None) == ControlType.SWITCH
        and getattr(original_desc, "data_type", None) == ModbusDataType.HOLDING_REGISTER
    ):
        if isinstance(original_desc, ModbusSwitchEntityDescription):
            conv_map = {getattr(original_desc, "on", None): "on", getattr(original_desc, "off", None): "off"}

    entity_category = getattr(original_desc, "entity_category", None)
    if entity_category == EntityCategory.CONFIG:
        entity_category = EntityCategory.DIAGNOSTIC  # Optionally, use None instead

    return MirroredSensorEntityDescription(
        key=original_desc.key + "_mirror",
        name=original_desc.name + " (Mirror)",
        register_address=original_desc.register_address,
        data_type=original_desc.data_type,
        register_count=original_desc.register_count,
        conv_sum_scale=getattr(original_desc, "conv_sum_scale", None),
        conv_multiplier=getattr(original_desc, "conv_multiplier", 1.0),
        conv_offset=getattr(original_desc, "conv_offset", None),
        conv_shift_bits=getattr(original_desc, "conv_shift_bits", None),
        conv_bits=getattr(original_desc, "conv_bits", None),
        conv_map=conv_map,
        conv_flags=getattr(original_desc, "conv_flags", None),
        is_string=getattr(original_desc, "is_string", False),
        is_float=getattr(original_desc, "is_float", False),
        precision=getattr(original_desc, "precision", None),
        never_resets=getattr(original_desc, "never_resets", False),
        control_type=ControlType.SENSOR,
        mirror_type=getattr(original_desc, "control_type", None),
        device_class=getattr(original_desc, "device_class", None),
        state_class=getattr(original_desc, "state_class", None),
        native_unit_of_measurement=getattr(original_desc, "native_unit_of_measurement", None),
        entity_category=entity_category,
        entity_registry_enabled_default=getattr(original_desc, "entity_registry_enabled_default", None),
    )


async def async_setup_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    control: ControlType,
    entity_class: type[ModbusCoordinatorEntity],
) -> None:
    """Set up the Modbus Connect sensors."""
    config: dict[str, Any] = {**config_entry.data}
    _LOGGER.debug(f"Setting up entities for config: {config}, platform: {control}")
    coordinator: ModbusCoordinator = hass.data[DOMAIN][get_gateway_key(config_entry)]
    # TODO: Maybe create ModbusDeviceInfo only once because here it is called with the same config multiple times for different platforms (probably not worth the hassle and storage needed in hass.data[DOMAIN])
    device_info: ModbusDeviceInfo = await hass.async_add_executor_job(create_device_info, config[CONF_FILENAME])

    coordinator.max_read_size = device_info.max_read_size

    identifiers = {(DOMAIN, coordinator.gateway)}
    # # This could also look like that if we want only one gateway per TCP gateway
    # identifiers: set[tuple[str, str]] = {
    #     (DOMAIN, f"{coordinator.gateway}-{config[CONF_SLAVE_ID]}"),
    # }

    device = DeviceInfo(
        identifiers=identifiers,
        name=" ".join(
            [part for part in [config.get(CONF_PREFIX), device_info.manufacturer, device_info.model] if part]
        ),
        manufacturer=device_info.manufacturer,
        model=device_info.model,
        via_device=list(coordinator.gateway_device.identifiers)[0],
    )

    _LOGGER.debug(device)

    descriptions = [desc for desc in device_info.entity_descriptions if desc.control_type == control]
    if control == ControlType.SENSOR and config_entry.options.get(
        OPTIONS_MIRROR_NON_SENSORS, OPTIONS_MIRROR_NON_SENSORS_DEFAULT
    ):
        # Collect (data_type, register_address) pairs for all existing sensor entities
        sensor_keys = {
            (desc.data_type, desc.register_address)
            for desc in device_info.entity_descriptions
            if desc.control_type == ControlType.SENSOR
        }

        # Filter non-sensor descriptions, excluding those with a matching sensor already defined
        non_sensor_descriptions = [
            desc
            for desc in device_info.entity_descriptions
            if desc.control_type != ControlType.SENSOR and (desc.data_type, desc.register_address) not in sensor_keys
        ]
        mirrored_descriptions = [create_mirrored_sensor_description(desc) for desc in non_sensor_descriptions]
        descriptions.extend(mirrored_descriptions)

    async_add_entities(
        [
            entity_class(
                coordinator=coordinator,
                ctx=ModbusContext(slave_id=config[CONF_SLAVE_ID], desc=desc),
                device=device,
            )
            for desc in descriptions
        ],
        update_before_add=False,
    )

    coordinator._recompute_read_plan = True
    await coordinator.async_config_entry_first_refresh()
