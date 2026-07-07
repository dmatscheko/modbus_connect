"""Discover and load device YAML files.

Built-in files live in ``device_configs/`` next to this module; users can add
their own (or override built-ins by using the same filename) in
``<ha_config>/modbus_connect/`` — that directory survives integration updates.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from homeassistant.core import HomeAssistant

from .const import USER_CONFIG_DIR
from .models import DeviceDef
from .schema import DeviceSchemaError, parse_device

_LOGGER = logging.getLogger(__name__)

BUILTIN_DIR = Path(__file__).parent / "device_configs"


def _discover(hass: HomeAssistant) -> dict[str, Path]:
    """Map lowercase filename -> path; user files override built-ins."""
    files: dict[str, Path] = {}
    user_dir = Path(hass.config.config_dir) / USER_CONFIG_DIR
    for directory in (BUILTIN_DIR, user_dir):
        if directory.is_dir():
            for path in sorted(directory.glob("*.yaml")):
                files[path.name.lower()] = path
    return files


def _load_file(path: Path, filename: str) -> DeviceDef:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return parse_device(data, filename=filename)


async def async_load_device(hass: HomeAssistant, filename: str) -> DeviceDef:
    """Load one device definition by filename; raises DeviceSchemaError."""
    files = await hass.async_add_executor_job(_discover, hass)
    path = files.get(filename.lower())
    if path is None:
        raise DeviceSchemaError(f"device file '{filename}' not found")
    try:
        return await hass.async_add_executor_job(_load_file, path, filename.lower())
    except yaml.YAMLError as err:
        raise DeviceSchemaError(f"{filename}: invalid YAML: {err}") from err


async def async_load_all(hass: HomeAssistant) -> dict[str, DeviceDef]:
    """Load every discoverable device definition, skipping invalid files."""
    files = await hass.async_add_executor_job(_discover, hass)
    devices: dict[str, DeviceDef] = {}
    for name, path in files.items():
        try:
            devices[name] = await hass.async_add_executor_job(_load_file, path, name)
        except (DeviceSchemaError, yaml.YAMLError, OSError) as err:
            _LOGGER.warning("Skipping device file %s: %s", path, err)
    return devices
