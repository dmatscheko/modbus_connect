"""Sensor tests"""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.modbus_connect.const import DOMAIN


@pytest.mark.nohomeassistant
async def test_setup_entry(hass) -> None:
    """Test the HA setup function"""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "name": "simple config",
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
