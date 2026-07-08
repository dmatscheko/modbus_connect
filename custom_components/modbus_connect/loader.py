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

# The libyaml-backed loader is ~7x faster than the pure-Python one; parsing all
# built-in device files drops from ~200 ms to ~30 ms. Fall back when the C
# extension isn't built.
try:
    from yaml import CSafeLoader as _YamlLoader
except ImportError:  # pragma: no cover - depends on the libyaml build
    from yaml import SafeLoader as _YamlLoader

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
        data = yaml.load(fh, Loader=_YamlLoader)
    return parse_device(data, filename=filename)


def _load_one(hass: HomeAssistant, filename: str) -> DeviceDef:
    """Discover and load a single device file. Runs entirely in one executor job."""
    path = _discover(hass).get(filename.lower())
    if path is None:
        raise DeviceSchemaError(f"device file '{filename}' not found")
    try:
        return _load_file(path, filename.lower())
    except yaml.YAMLError as err:
        raise DeviceSchemaError(f"{filename}: invalid YAML: {err}") from err


def _load_all(hass: HomeAssistant) -> dict[str, DeviceDef]:
    """Discover and load every device file. Runs entirely in one executor job."""
    devices: dict[str, DeviceDef] = {}
    for name, path in _discover(hass).items():
        try:
            devices[name] = _load_file(path, name)
        except (DeviceSchemaError, yaml.YAMLError, OSError) as err:
            _LOGGER.warning("Skipping device file %s: %s", path, err)
    return devices


async def async_load_device(hass: HomeAssistant, filename: str) -> DeviceDef:
    """Load one device definition by filename; raises DeviceSchemaError."""
    return await hass.async_add_executor_job(_load_one, hass, filename)


async def async_load_all(hass: HomeAssistant) -> dict[str, DeviceDef]:
    """Load every discoverable device definition, skipping invalid files."""
    return await hass.async_add_executor_job(_load_all, hass)
