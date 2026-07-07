"""Device file discovery and loading."""

from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant

from custom_components.modbus_connect.loader import async_load_all, async_load_device
from custom_components.modbus_connect.schema import DeviceSchemaError

GOOD = """
device: {manufacturer: Acme, model: X1}
holding:
  t: {address: 0, ha: {platform: sensor}}
"""


def user_dir(hass: HomeAssistant) -> Path:
    directory = Path(hass.config.config_dir) / "modbus_connect"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


async def test_missing_file(hass: HomeAssistant) -> None:
    with pytest.raises(DeviceSchemaError, match="not found"):
        await async_load_device(hass, "ghost.yaml")


async def test_invalid_yaml_reported(hass: HomeAssistant) -> None:
    (user_dir(hass) / "broken.yaml").write_text("{:", encoding="utf-8")
    with pytest.raises(DeviceSchemaError, match="invalid YAML"):
        await async_load_device(hass, "broken.yaml")


async def test_load_all_skips_invalid_files(hass: HomeAssistant) -> None:
    directory = user_dir(hass)
    (directory / "good.yaml").write_text(GOOD, encoding="utf-8")
    (directory / "broken.yaml").write_text("{:", encoding="utf-8")
    (directory / "bad_schema.yaml").write_text("device: {}", encoding="utf-8")

    devices = await async_load_all(hass)
    assert "good.yaml" in devices
    assert "broken.yaml" not in devices
    assert "bad_schema.yaml" not in devices


async def test_user_file_overrides_builtin(hass: HomeAssistant) -> None:
    (user_dir(hass) / "test.yaml").write_text(GOOD, encoding="utf-8")
    device = await async_load_device(hass, "Test.yaml")  # lookup is case-insensitive
    assert device.manufacturer == "Acme"
