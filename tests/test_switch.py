"""Switch tests"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.modbus_connect.const import DOMAIN
from custom_components.modbus_connect.context import ModbusContext
from custom_components.modbus_connect.entity_management.base import (
    ModbusSwitchEntityDescription,
)
from custom_components.modbus_connect.entity_management.modbus_device_info import (
    ModbusDeviceInfo,
)
from custom_components.modbus_connect.switch import (
    ModbusSwitchEntity,
    async_setup_entry,
)


@pytest.mark.nohomeassistant
async def test_setup_entry(hass) -> None:
    """Test the HA setup function"""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "127.0.0.1",
            "port": "1234",
            "slave_id": 1,
            "filename": "test.yaml",
        },
    )
    callback = MagicMock()
    coordinator = AsyncMock()
    gw_dev = MagicMock()
    type(coordinator).gateway_device = PropertyMock(return_value=gw_dev)
    identifiers = PropertyMock()
    identifiers.return_value = ["a"]
    type(gw_dev).identifiers = identifiers
    hass.data[DOMAIN] = {"127.0.0.1:1234:1": coordinator}

    pm1 = PropertyMock(
        return_value=[
            ModbusSwitchEntityDescription(key="coil_rw", register_address=1, data_type="coil", control_type="switch"),
            ModbusSwitchEntityDescription(
                key="reg_rw", register_address=2, data_type="holding_register", control_type="switch", on=1, off=0
            ),
        ]
    )
    pm2 = PropertyMock(return_value="")

    with patch(
        "custom_components.modbus_connect.sensor_types.modbus_device_info.load_yaml",
        return_value={"device": MagicMock()},
    ), patch.object(ModbusDeviceInfo, "entity_descriptions", pm1), patch.object(
        ModbusDeviceInfo, "manufacturer", pm2
    ), patch.object(
        ModbusDeviceInfo, "model", pm2
    ):
        await async_setup_entry(hass, entry, callback.add)

        callback.add.assert_called_once()
        assert len(callback.add.call_args[0][0]) == 2  # Coil and Holding Register switches
        assert callback.add.call_args[1] == {"update_before_add": False}
        pm1.assert_called_once()


async def test_update_none() -> None:
    """Test the coordinator update function"""
    coordinator = MagicMock()
    ctx = ModbusContext(
        1,
        ModbusEntityDescription(  # pylint: disable=unexpected-keyword-arg
            register_address=1,
            key="key",
        ),
    )
    device = MagicMock()
    entity = ModbusSwitchEntity(coordinator=coordinator, ctx=ctx, device=device)

    coordinator.get_data.return_value = None
    entity._handle_coordinator_update()  # pylint: disable=protected-access

    coordinator.get_data.assert_called_once_with(ctx)


async def test_update_exception() -> None:
    """Test the coordinator update function"""
    coordinator = MagicMock()
    ctx = ModbusContext(
        1,
        ModbusEntityDescription(  # pylint: disable=unexpected-keyword-arg
            register_address=1,
            key="key",
        ),
    )
    device = MagicMock()
    entity = ModbusSwitchEntity(coordinator=coordinator, ctx=ctx, device=device)
    type(entity).name = PropertyMock(return_value="Test")
    coordinator.get_data.side_effect = Exception()

    with patch("custom_components.modbus_connect.switch._LOGGER.warning") as warning, patch(
        "custom_components.modbus_connect.switch._LOGGER.debug"
    ) as debug, patch("custom_components.modbus_connect.switch._LOGGER.error") as error:
        entity._handle_coordinator_update()  # pylint: disable=protected-access

        coordinator.get_data.assert_called_once_with(ctx)

        debug.assert_not_called()
        warning.assert_not_called()
        error.assert_called_once()


async def test_update_value() -> None:
    """Test the coordinator update function"""
    coordinator = MagicMock()
    ctx = ModbusContext(
        1,
        ModbusEntityDescription(  # pylint: disable=unexpected-keyword-arg
            register_address=1,
            key="key",
        ),
    )
    device = MagicMock()
    entity = ModbusSwitchEntity(coordinator=coordinator, ctx=ctx, device=device)
    type(entity).name = PropertyMock(return_value="Test")
    type(entity).entity_description = PropertyMock(
        return_value=ModbusSwitchEntityDescription(  # pylint: disable=unexpected-keyword-arg
            key="key",
            register_address=1,
            control_type="switch",
            on=1,
            off=2,
        )
    )
    coordinator.get_data.return_value = 1
    write = MagicMock()
    entity.async_write_ha_state = write

    with patch("custom_components.modbus_connect.switch._LOGGER.warning") as warning, patch(
        "custom_components.modbus_connect.switch._LOGGER.debug"
    ) as debug, patch("custom_components.modbus_connect.switch._LOGGER.error") as error:
        entity._handle_coordinator_update()  # pylint: disable=protected-access

        coordinator.get_data.assert_called_once_with(ctx)

        error.assert_not_called()
        debug.assert_called_once()
        warning.assert_not_called()
        write.assert_called_once()


async def test_update_deviceupdate() -> None:
    """Test the coordinator update function"""
    coordinator = MagicMock()
    ctx = ModbusContext(
        1,
        ModbusEntityDescription(  # pylint: disable=unexpected-keyword-arg
            register_address=1,
            key="key",
        ),
    )
    device = MagicMock()
    hass = MagicMock()
    entity = ModbusSwitchEntity(coordinator=coordinator, ctx=ctx, device=device)
    type(entity).name = PropertyMock(return_value="Test")
    type(entity).hass = PropertyMock(return_value=hass)
    type(entity).native_value = PropertyMock(return_value=2)  # type: ignore
    type(entity).entity_description = PropertyMock(
        return_value=ModbusSwitchEntityDescription(  # pylint: disable=unexpected-keyword-arg
            key="switch",
            register_address=1,
            control_type="switch",
            on=1,
            off=2,
        )
    )

    write = MagicMock()
    entity.async_write_ha_state = write

    coordinator.get_data.return_value = 1

    with patch("custom_components.modbus_connect.switch._LOGGER.warning") as warning, patch(
        "custom_components.modbus_connect.switch._LOGGER.debug"
    ) as debug, patch("custom_components.modbus_connect.switch._LOGGER.error") as error:

        entity._handle_coordinator_update()  # pylint: disable=protected-access

        coordinator.get_data.assert_called_once_with(ctx)

        error.assert_not_called()
        debug.assert_called()
        warning.assert_not_called()
        write.assert_called_once()
