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


def _read_device_head(path: Path) -> str:
    """The YAML text from the top of a device file down to (excluding) the first
    section key after ``device:`` — the header comments plus the ``device:`` block,
    which is valid YAML on its own.

    Read lazily and stopped early: the picker needs only manufacturer/model, so a
    6000-line device file yields ~15 lines and its (large) entity map is never
    touched. Listing every device stays roughly O(number of files), not O(bytes).
    """
    lines: list[str] = []
    seen_device = False
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            # A section key sits in column 0 (entities/translations are indented,
            # comments start with '#'); the first one after device: ends the block.
            top_level_key = line[:1].isalpha() or line[:1] == "_"
            if seen_device and top_level_key and not line.startswith("device:"):
                break
            if line.startswith("device:"):
                seen_device = True
            lines.append(line)
    return "".join(lines)


def _device_label(path: Path, filename: str) -> tuple[str, str]:
    """``(manufacturer, model)`` read from just the ``device:`` block — no entity
    parse, no schema validation (that happens on selection via async_load_device).
    Raises DeviceSchemaError if the block is unreadable or lacks either field.
    """
    try:
        data = yaml.load(_read_device_head(path), Loader=_UniqueKeyLoader) or {}
    except yaml.YAMLError as err:
        raise DeviceSchemaError(f"{filename}: invalid YAML: {' '.join(str(err).split())}") from err
    except OSError as err:
        raise DeviceSchemaError(f"{filename}: cannot read: {err}") from err
    device = data.get("device")
    if not isinstance(device, dict) or not device.get("manufacturer") or not device.get("model"):
        raise DeviceSchemaError(f"{filename}: device.manufacturer and device.model are required")
    return str(device["manufacturer"]), str(device["model"])


def _list_all(hass: HomeAssistant) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    """Discover every device file and read just its manufacturer/model, in one
    executor job. Returns filename -> (manufacturer, model), plus filename -> reason
    for files whose ``device:`` block is missing/unreadable (kept out of the picker).
    """
    devices: dict[str, tuple[str, str]] = {}
    errors: dict[str, str] = {}
    for name, path in _discover(hass).items():
        try:
            devices[name] = _device_label(path, name)
        except DeviceSchemaError as err:
            _LOGGER.warning("Skipping device file %s: %s", path, err)
            errors[name] = str(err)
    return devices, errors


async def async_load_device(hass: HomeAssistant, filename: str) -> DeviceDef:
    """Load one device definition by filename; raises DeviceSchemaError."""
    return await hass.async_add_executor_job(_load_one, hass, filename)


async def async_list_devices(
    hass: HomeAssistant,
) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    """Fast picker data: filename -> (manufacturer, model), read from each file's
    ``device:`` block only — never its entity map. The full parse + validation of
    the chosen file happens on selection via :func:`async_load_device`.

    Also returns filename -> reason for files whose ``device:`` block could not be
    read, so the config flow can list them instead of dropping them silently. An
    entity-level error in an otherwise-listable file surfaces on selection instead.
    """
    return await hass.async_add_executor_job(_list_all, hass)
