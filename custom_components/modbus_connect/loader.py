"""Discover and load device YAML files.

Built-in files live in ``device_configs/`` next to this module; users can add
their own (or override built-ins by using the same filename) in
``<ha_config>/modbus_connect/`` — that directory survives integration updates.
"""

from __future__ import annotations

import logging
from collections.abc import Hashable
from pathlib import Path
from typing import Any

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
    from yaml import SafeLoader as _YamlLoader  # type: ignore[assignment]

_LOGGER = logging.getLogger(__name__)

BUILTIN_DIR = Path(__file__).parent / "device_configs"


class _UniqueKeyLoader(_YamlLoader):
    """Reject duplicate mapping keys.

    YAML silently keeps only the last duplicate, so an entity defined twice in
    the same section would validate cleanly while one definition is dropped —
    invisible to the author. Refuse with the key and line named instead.
    """

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        for key_node, _value in node.value:
            key = self.construct_object(key_node, deep=deep)
            if isinstance(key, Hashable):
                if key in seen:
                    raise yaml.constructor.ConstructorError(
                        None, None, f"duplicate key {key!r}", key_node.start_mark
                    )
                seen.add(key)
        return super().construct_mapping(node, deep)


def _discover(hass: HomeAssistant) -> dict[str, Path]:
    """Map lowercase filename -> path; user files override built-ins."""
    files: dict[str, Path] = {}
    user_dir = Path(hass.config.config_dir) / USER_CONFIG_DIR
    for directory in (BUILTIN_DIR, user_dir):
        if directory.is_dir():
            for path in sorted(directory.glob("*.yaml")):
                files[path.name.lower()] = path
    return files


def _load_file(path: Path, filename: str, language: str = "en") -> DeviceDef:
    with path.open(encoding="utf-8") as fh:
        data = yaml.load(fh, Loader=_UniqueKeyLoader)  # a SafeLoader subclass
    return parse_device(data, filename=filename, language=language)


def _load_one(hass: HomeAssistant, filename: str) -> DeviceDef:
    """Discover and load a single device file. Runs entirely in one executor job."""
    path = _discover(hass).get(filename.lower())
    if path is None:
        raise DeviceSchemaError(f"device file '{filename}' not found")
    try:
        return _load_file(path, filename.lower(), hass.config.language)
    except yaml.YAMLError as err:
        raise DeviceSchemaError(f"{filename}: invalid YAML: {err}") from err
    except OSError as err:
        # An unreadable file must surface as a config-entry error message, the
        # same way _load_all reports it, not as a raw traceback.
        raise DeviceSchemaError(f"{filename}: cannot read: {err}") from err


def _load_all(hass: HomeAssistant) -> tuple[dict[str, DeviceDef], dict[str, str]]:
    """Discover and load every device file. Runs entirely in one executor job."""
    devices: dict[str, DeviceDef] = {}
    errors: dict[str, str] = {}
    language = hass.config.language
    for name, path in _discover(hass).items():
        try:
            devices[name] = _load_file(path, name, language)
        except (DeviceSchemaError, yaml.YAMLError, OSError) as err:
            _LOGGER.warning("Skipping device file %s: %s", path, err)
            # One line per file; schema errors already lead with the filename
            message = " ".join(str(err).split())
            errors[name] = message if message.startswith(name) else f"{name}: {message}"
    return devices, errors


async def async_load_device(hass: HomeAssistant, filename: str) -> DeviceDef:
    """Load one device definition by filename; raises DeviceSchemaError."""
    return await hass.async_add_executor_job(_load_one, hass, filename)


async def async_load_all(
    hass: HomeAssistant,
) -> tuple[dict[str, DeviceDef], dict[str, str]]:
    """Load every discoverable device definition, skipping invalid files.

    Returns the loaded definitions plus filename -> reason for every skipped
    file, so the config flow can say *why* a file is missing from the picker
    instead of leaving the author to dig through the log.
    """
    return await hass.async_add_executor_job(_load_all, hass)
