"""Parse and validate device YAML files into :class:`DeviceDef`.

Modbus concerns live at the top level of each entity; everything Home
Assistant lives in the ``ha:`` block, which is validated against the real
per-platform ``EntityDescription`` dataclass — any field HA supports (now or
in a future release) can be set there, and typos are rejected with the file
and entity named.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.button import ButtonDeviceClass, ButtonEntityDescription
from homeassistant.components.climate import ClimateEntityDescription, HVACMode
from homeassistant.components.cover import CoverDeviceClass, CoverEntityDescription
from homeassistant.components.fan import FanEntityDescription
from homeassistant.components.light import LightEntityDescription
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntityDescription
from homeassistant.components.text import TextEntityDescription, TextMode
from homeassistant.components.time import TimeEntityDescription
from homeassistant.components.valve import ValveDeviceClass, ValveEntityDescription
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory, EntityDescription

from .const import BASIC_GROUP, DEFAULT_MAX_GAP, DEFAULT_MAX_READ
from .models import (
    BIT_TABLES,
    FLOAT_TYPES,
    PLATFORMS,
    SWAP_MODES,
    TABLES,
    TEMPLATE_PLATFORMS,
    TYPE_ALIASES,
    TYPE_BITS,
    TYPE_STRING,
    TYPE_TIME,
    TYPE_WIDTH,
    WRITABLE_TABLES,
    DeviceDef,
    EntityDef,
    SwitchTarget,
    TemplateDef,
    WriteTarget,
)

DESCRIPTION_CLASSES: dict[str, type[EntityDescription]] = {
    "sensor": SensorEntityDescription,
    "binary_sensor": BinarySensorEntityDescription,
    "number": NumberEntityDescription,
    "select": SelectEntityDescription,
    "switch": SwitchEntityDescription,
    "text": TextEntityDescription,
    "time": TimeEntityDescription,
    "button": ButtonEntityDescription,
    "valve": ValveEntityDescription,
    # template: section only
    "climate": ClimateEntityDescription,
    "cover": CoverEntityDescription,
    "fan": FanEntityDescription,
    "light": LightEntityDescription,
}

# Friendly YAML names -> EntityDescription field names
HA_ALIASES: dict[str, str] = {
    "unit_of_measurement": "native_unit_of_measurement",
    "unit": "native_unit_of_measurement",
    "min": "native_min_value",
    "max": "native_max_value",
    "step": "native_step",
    "precision": "suggested_display_precision",
    "enabled_by_default": "entity_registry_enabled_default",
}

# Fields coerced into HA enums (typo checking with helpful messages)
_ENUM_FIELDS: dict[str, dict[str, type]] = {
    "sensor": {"device_class": SensorDeviceClass, "state_class": SensorStateClass},
    "binary_sensor": {"device_class": BinarySensorDeviceClass},
    "number": {"device_class": NumberDeviceClass, "mode": NumberMode},
    "switch": {"device_class": SwitchDeviceClass},
    "button": {"device_class": ButtonDeviceClass},
    "text": {"mode": TextMode},
    "cover": {"device_class": CoverDeviceClass},
    "valve": {"device_class": ValveDeviceClass},
}

_OLD_FORMAT_SECTIONS = {
    "read_write_word",
    "read_only_word",
    "read_write_boolean",
    "read_only_boolean",
}

_MODBUS_KEYS = {
    "address",
    "internal",
    "type",
    "count",
    "swap",
    "sum_scale",
    "mask",
    "multiplier",
    "offset",
    "map",
    "flags",
    "on_value",
    "off_value",
    "write_value",
    "read_register",
    "static_value",
    "optimistic_default",
    "write_multiple",
    "confirm_delay",
    "rectify_time",
    "read_modify_write",
    "max_change",
    "never_resets",
    "scan_interval",
    "duplicate_as_sensor",
    "groups",
    "ha",
}


class DeviceSchemaError(Exception):
    """A device YAML file is invalid; the message names file and entity."""


class _Ctx:
    """Error-message context (filename + entity key) plus the translation lookup.

    ``localize`` maps a human-facing source string to its translation for the
    target language; it is identity for standalone callers and for files without
    a ``translations:`` block, so single-language files behave exactly as before.
    """

    def __init__(
        self,
        filename: str,
        key: str = "",
        localize: Callable[[str], str] | None = None,
    ) -> None:
        self.filename = filename
        self.key = key
        self.localize: Callable[[str], str] = localize or (lambda text: text)

    def fail(self, message: str) -> DeviceSchemaError:
        where = f"{self.filename}: " if self.filename else ""
        if self.key:
            where += f"entity '{self.key}': "
        return DeviceSchemaError(where + message)


def _parse_translations(ctx: _Ctx, raw: Any) -> dict[str, dict[str, str]]:
    """Parse the optional top-level ``translations:`` block.

    Maps a source string (as written elsewhere in the file, typically English)
    to a ``{language code: text}`` mapping. Absent -> ``{}``, meaning every
    string is used verbatim.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict) or not raw:
        raise ctx.fail(
            "'translations' must be a non-empty mapping of source text -> "
            "{language: text}"
        )
    out: dict[str, dict[str, str]] = {}
    for src, langs in raw.items():
        if not isinstance(src, str) or not src:
            raise ctx.fail(f"translations keys must be non-empty strings, got {src!r}")
        if not isinstance(langs, dict) or not langs:
            raise ctx.fail(
                f"translations[{src!r}] must be a non-empty mapping of "
                "language code -> text"
            )
        entry: dict[str, str] = {}
        for lang, text in langs.items():
            if not isinstance(lang, str) or not lang.strip():
                raise ctx.fail(
                    f"translations[{src!r}] language codes must be non-empty "
                    f"strings, got {lang!r}"
                )
            if not isinstance(text, str) or not text:
                raise ctx.fail(
                    f"translations[{src!r}][{lang!r}] must be a non-empty string"
                )
            entry[lang] = text
        out[src] = entry
    return out


def _make_localizer(
    catalog: dict[str, dict[str, str]], language: str
) -> Callable[[str], str]:
    """Build the source-string -> translation function for ``language``.

    Resolution tries the full language tag, then its primary subtag
    (``de-DE`` -> ``de``), then English; a string that is absent from the
    catalog (and every string when the catalog is empty) is returned unchanged.
    """
    order: list[str] = []
    for lang in (language, language.split("-")[0], "en"):
        if lang and lang not in order:
            order.append(lang)

    def localize(text: str) -> str:
        entry = catalog.get(text)
        if entry is None:
            return text
        for lang in order:
            translated = entry.get(lang)
            if translated is not None:
                return translated
        return text

    return localize


def parse_device(data: Any, filename: str = "", language: str = "en") -> DeviceDef:
    """Validate a loaded YAML document and build a DeviceDef.

    ``language`` selects which entry of each ``translations:`` mapping to use for
    human-facing strings (device model, group labels, entity names, map/flag
    values), falling back to English and then to the source string. It defaults
    to English so standalone callers (the converter, tests) need not pass it.
    """
    ctx = _Ctx(filename)
    if not isinstance(data, dict):
        raise ctx.fail("file does not contain a YAML mapping")
    if _OLD_FORMAT_SECTIONS & set(data):
        raise ctx.fail(
            "this looks like an old modbus_local_gateway device file; "
            "convert it with support/converter/modbus_local_gateway/"
            "modbus_local_gateway-convert.py first"
        )
    unknown = set(data) - {"device", "template", "translations", *TABLES}
    if unknown:
        raise ctx.fail(
            f"unknown top-level keys: {sorted(unknown)} "
            f"(entities live in {'/'.join(TABLES)} sections)"
        )

    catalog = _parse_translations(ctx, data.get("translations"))
    ctx.localize = _make_localizer(catalog, language)

    device = data.get("device")
    if not isinstance(device, dict):
        raise ctx.fail("missing 'device:' section")
    device_fields = _parse_device_block(ctx, device)
    entities = _parse_sections(ctx, data, filename)
    templates = _parse_templates(ctx, data, entities, filename)

    declared_groups = {g for e in entities for g in e.groups} | {
        g for t in templates for g in t.groups
    }
    # The reserved "basic" group needs no tags: it is always enabled, so it is
    # a valid default in any grouped file.
    unknown_defaults = (
        set(device_fields["default_groups"]) - declared_groups - {BASIC_GROUP}
    )
    if unknown_defaults:
        raise ctx.fail(
            f"device.default_groups {sorted(unknown_defaults)} name groups no entity "
            f"uses (declared groups: {sorted(declared_groups)})"
        )
    unknown_labels = (
        {g for g, _ in device_fields["group_labels"]} - declared_groups - {BASIC_GROUP}
    )
    if unknown_labels:
        raise ctx.fail(
            f"device.group_labels {sorted(unknown_labels)} name groups no entity "
            f"uses (declared groups: {sorted(declared_groups)})"
        )

    return DeviceDef(
        entities=tuple(entities),
        templates=tuple(templates),
        filename=filename,
        **device_fields,
    )


def _parse_device_block(ctx: _Ctx, device: dict[str, Any]) -> dict[str, Any]:
    """Validate the device: section; returns the device-level DeviceDef fields."""
    for required in ("manufacturer", "model"):
        if not isinstance(device.get(required), str) or not device[required]:
            raise ctx.fail(f"device.{required} is required and must be a string")
    unknown = set(device) - {
        "manufacturer",
        "model",
        "max_register_read",
        "max_read_gap",
        "bad_addresses",
        "split_before",
        "scan_interval",
        "min_scan_interval",
        "timeout",
        "retries",
        "request_delay",
        "modbus_id",
        "prefix",
        "sw_version",
        "hw_version",
        "serial_number",
        "default_groups",
        "group_labels",
    }
    if unknown:
        raise ctx.fail(f"unknown device keys: {sorted(unknown)}")
    scan_interval = device.get("scan_interval")
    if scan_interval is not None:
        scan_interval = _int_in_range(ctx, "device.scan_interval", scan_interval, 1, 86400)
    min_scan_interval = device.get("min_scan_interval")
    if min_scan_interval is not None:
        min_scan_interval = _int_in_range(
            ctx, "device.min_scan_interval", min_scan_interval, 1, 86400
        )
    timeout = device.get("timeout")
    if timeout is not None:
        timeout = _number(ctx, "device.timeout", timeout)
        if not 0 < timeout <= 60:
            raise ctx.fail("device.timeout must be > 0 and <= 60 seconds")
    retries = device.get("retries")
    if retries is not None:
        retries = _int_in_range(ctx, "device.retries", retries, 0, 10)
    request_delay = device.get("request_delay")
    if request_delay is not None:
        request_delay = _number(ctx, "device.request_delay", request_delay)
        if not 0 <= request_delay <= 5:
            raise ctx.fail("device.request_delay must be between 0 and 5 seconds")
    bad_addresses = _parse_address_hints(ctx, device, "bad_addresses")
    boundaries = _parse_address_hints(ctx, device, "split_before")
    modbus_id = device.get("modbus_id")
    if modbus_id is not None:
        modbus_id = _int_in_range(ctx, "device.modbus_id", modbus_id, 0, 255)
    prefix = device.get("prefix")
    if prefix is not None and (not isinstance(prefix, str) or not prefix):
        raise ctx.fail("device.prefix must be a non-empty string")
    # Device-info fields are template strings (rendered from the first read).
    info: dict[str, str | None] = {}
    for key in ("sw_version", "hw_version", "serial_number"):
        value = device.get(key)
        if value is not None and (not isinstance(value, str) or not value):
            raise ctx.fail(f"device.{key} must be a non-empty string (may be a template)")
        info[key] = value
    default_groups = _parse_groups(ctx, "device.default_groups", device.get("default_groups"))
    group_labels = _parse_group_labels(ctx, device.get("group_labels"))
    return {
        "manufacturer": device["manufacturer"],
        "model": ctx.localize(device["model"]),
        "max_read": _int_in_range(ctx, "device.max_register_read",
                                  device.get("max_register_read", DEFAULT_MAX_READ), 1, 2000),
        "max_gap": _int_in_range(ctx, "device.max_read_gap",
                                 device.get("max_read_gap", DEFAULT_MAX_GAP), 0, 1000),
        "bad_addresses": bad_addresses,
        "boundaries": boundaries,
        "scan_interval": scan_interval,
        "min_scan_interval": min_scan_interval,
        "timeout": timeout,
        "retries": retries,
        "request_delay": request_delay,
        "modbus_id": modbus_id,
        "prefix": prefix,
        "default_groups": default_groups,
        "group_labels": group_labels,
        **info,
    }


def _parse_address_hints(
    ctx: _Ctx, device: dict[str, Any], key: str
) -> frozenset[tuple[str, int]]:
    """Parse a ``{table: [addresses]}`` read-planning hint into (table, addr) pairs."""
    raw = device.get(key)
    if raw is None:
        return frozenset()
    if not isinstance(raw, dict) or not raw:
        raise ctx.fail(
            f"device.{key} must be a mapping of table -> address list, "
            f"e.g. {{holding: [5, 7]}}"
        )
    out: set[tuple[str, int]] = set()
    for table, addrs in raw.items():
        if table not in TABLES:
            raise ctx.fail(
                f"device.{key}: unknown table {table!r} (expected one of {list(TABLES)})"
            )
        if not isinstance(addrs, list) or not addrs:
            raise ctx.fail(f"device.{key}.{table} must be a non-empty list of addresses")
        for addr in addrs:
            out.add((table, _int_in_range(ctx, f"device.{key}.{table}", addr, 0, 0xFFFF)))
    return frozenset(out)


def _parse_sections(ctx: _Ctx, data: dict[str, Any], filename: str) -> list[EntityDef]:
    """Parse the four table sections into entity definitions."""
    entities: list[EntityDef] = []
    section_of: dict[str, str] = {}
    for section in TABLES:
        block = data.get(section)
        if block is None:
            continue
        if not isinstance(block, dict):
            raise ctx.fail(f"'{section}:' must be a mapping of entity definitions")
        for key, raw in block.items():
            key = str(key)
            if key in section_of:
                raise ctx.fail(
                    f"entity '{key}' is defined in both '{section_of[key]}:' and "
                    f"'{section}:' — keys must be unique across sections"
                )
            section_of[key] = section
            entities.append(
                _parse_entity(_Ctx(filename, key, ctx.localize), key, raw, section)
            )

    if not entities:
        raise ctx.fail(
            f"no entities defined (add one of the {'/'.join(TABLES)} sections)"
        )
    return entities


def _parse_templates(
    ctx: _Ctx, data: dict[str, Any], entities: list[EntityDef], filename: str
) -> list[TemplateDef]:
    """Parse the template: section against the already-parsed entities."""
    raw_templates = data.get("template") or {}
    if not isinstance(raw_templates, dict):
        raise ctx.fail("'template:' must be a mapping")
    defs_by_key = {e.key: e for e in entities}
    templates: list[TemplateDef] = []
    for key, raw in raw_templates.items():
        key = str(key)
        if key in defs_by_key:
            raise ctx.fail(
                f"template '{key}' collides with an entity of the same name"
            )
        templates.append(
            _parse_template(_Ctx(filename, key, ctx.localize), key, raw, defs_by_key)
        )
    return templates


def _int_in_range(ctx: _Ctx, name: str, value: Any, lo: int, hi: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
        raise ctx.fail(f"{name} must be an integer between {lo} and {hi}, got {value!r}")
    return value


def _number(ctx: _Ctx, name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ctx.fail(f"{name} must be a number, got {value!r}")
    return value


def _parse_groups(ctx: _Ctx, name: str, raw: Any) -> tuple[str, ...]:
    """A list of group names (deduped, order preserved); () when absent."""
    if raw is None:
        return ()
    if not isinstance(raw, list) or not raw:
        raise ctx.fail(f"'{name}' must be a non-empty list of group names")
    seen: dict[str, None] = {}
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ctx.fail(f"'{name}' entries must be non-empty strings, got {item!r}")
        seen.setdefault(item, None)
    return tuple(seen)


def _parse_group_labels(ctx: _Ctx, raw: Any) -> tuple[tuple[str, str], ...]:
    """Optional ``{group: display label}`` overrides for the group switches; ()
    when absent. Keys are checked against the file's declared groups by the caller."""
    if raw is None:
        return ()
    if not isinstance(raw, dict) or not raw:
        raise ctx.fail("'device.group_labels' must be a non-empty mapping of group -> label")
    out: list[tuple[str, str]] = []
    for name, label in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise ctx.fail(f"device.group_labels keys must be non-empty strings, got {name!r}")
        if not isinstance(label, str) or not label.strip():
            raise ctx.fail(f"device.group_labels[{name!r}] must be a non-empty string label")
        out.append((name, ctx.localize(label)))
    return tuple(out)


def _parse_entity(ctx: _Ctx, key: str, raw: Any, table: str) -> EntityDef:
    if not isinstance(raw, dict):
        raise ctx.fail("entity must be a mapping")
    if "table" in raw:
        raise ctx.fail(
            "'table' is not an entity key — entities are grouped by the "
            f"{'/'.join(TABLES)} sections instead"
        )
    # An unquoted `on:`/`off:` key is a YAML 1.1 *boolean*, not a string — the
    # reason these fields are named on_value/off_value. Catch both spellings of
    # the old name with a pointed hint instead of an "unknown key" puzzle.
    if any(k is True or k is False or k in ("on", "off") for k in raw):
        raise ctx.fail(
            "'on'/'off' are named 'on_value'/'off_value' (unquoted on/off are "
            "YAML booleans, so the short names would need quoting)"
        )
    unknown = set(raw) - _MODBUS_KEYS
    if unknown:
        raise ctx.fail(
            f"unknown keys: {sorted(unknown)} (Home Assistant fields go under 'ha:')"
        )

    platform, parsed_ha = _parse_platform(ctx, raw)

    address = raw.get("address")
    if address is None:
        raise ctx.fail("'address' is required")
    address = _int_in_range(ctx, "address", address, 0, 0xFFFF)

    typ, count, sum_scale, swap = _parse_shape(ctx, raw, table)
    if address + count > 0x10000:
        raise ctx.fail(
            f"address {address} + count {count} runs past the last address 65535"
        )
    mask, multiplier, offset, value_map, flags = _parse_conversions(
        ctx, raw, typ, count, sum_scale, swap
    )

    read_modify_write = _bool(ctx, raw, "read_modify_write")
    if read_modify_write and (mask is None or count != 1):
        raise ctx.fail("'read_modify_write' requires a 'mask' on a single register")

    max_change = raw.get("max_change")
    if max_change is not None:
        max_change = _number(ctx, "max_change", max_change)
        if max_change < 0:
            raise ctx.fail("max_change must be >= 0")

    scan_interval = raw.get("scan_interval")
    if scan_interval is not None:
        scan_interval = _int_in_range(ctx, "scan_interval", scan_interval, 1, 86400)

    on_value = _on_off(ctx, raw, "on_value")
    off_value = _on_off(ctx, raw, "off_value")

    write_value = _parse_write_value(ctx, raw.get("write_value"))

    read_register = raw.get("read_register")
    if read_register is not None and not isinstance(read_register, str):
        raise ctx.fail("read_register must be a template string, e.g. '{{ other_key }}'")

    write_multiple = _bool(ctx, raw, "write_multiple")
    confirm_delay = raw.get("confirm_delay")
    if confirm_delay is not None:
        confirm_delay = _number(ctx, "confirm_delay", confirm_delay)
        if not 0 < confirm_delay <= 10:
            raise ctx.fail("confirm_delay must be > 0 and <= 10 seconds")
    rectify_time = _bool(ctx, raw, "rectify_time")
    static_value = raw.get("static_value")
    if "static_value" in raw and not isinstance(static_value, (int, float, bool, str)):
        raise ctx.fail(
            "static_value must be a number, boolean, or string (the value the entity "
            "shows; its presence marks the register write-only)"
        )
    optimistic_default = raw.get("optimistic_default")
    if "optimistic_default" in raw and not isinstance(optimistic_default, (int, float, bool, str)):
        raise ctx.fail(
            "optimistic_default must be a number, boolean, or string (the fallback value "
            "shown when the register decodes to nothing)"
        )
    # A string here is a map label the entity shows (e.g. a select's seed), so it
    # must localize in lockstep with the map values — otherwise a translated
    # file's select never matches its options and shows "unknown".
    if isinstance(static_value, str):
        static_value = ctx.localize(static_value)
    if isinstance(optimistic_default, str):
        optimistic_default = ctx.localize(optimistic_default)

    duplicate_as_sensor = _bool(ctx, raw, "duplicate_as_sensor")
    groups = _parse_groups(ctx, "groups", raw.get("groups"))

    defn = EntityDef(
        key=key,
        platform=platform,
        table=table,
        address=address,
        type=typ,
        count=count,
        swap=swap,
        sum_scale=sum_scale,
        mask=mask,
        multiplier=multiplier,
        offset=offset,
        value_map=value_map,
        flags=flags,
        on_value=on_value,
        off_value=off_value,
        write_value=write_value,
        read_register=read_register,
        static_value=static_value,
        optimistic_default=optimistic_default,
        write_multiple=write_multiple,
        confirm_delay=confirm_delay,
        rectify_time=rectify_time,
        read_modify_write=read_modify_write,
        max_change=max_change,
        never_resets=_bool(ctx, raw, "never_resets"),
        scan_interval=scan_interval,
        duplicate_as_sensor=duplicate_as_sensor,
        groups=groups,
        ha=parsed_ha,
    )
    if not defn.internal:
        _check_platform_semantics(ctx, defn)
    return defn


def _parse_platform(ctx: _Ctx, raw: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """The entity's platform and validated ha: fields; ('internal', {}) for internal."""
    internal = _bool(ctx, raw, "internal")
    ha_raw = raw.get("ha")
    if internal:
        if ha_raw is not None:
            raise ctx.fail(
                "internal entities must not have an 'ha:' block "
                "(they exist only for the template: section)"
            )
        for bad in (
            "on_value", "off_value", "write_value", "static_value",
            "optimistic_default", "write_multiple", "confirm_delay",
        ):
            if raw.get(bad) is not None:
                raise ctx.fail(f"'{bad}' is not valid for internal entities")
        if raw.get("duplicate_as_sensor"):
            raise ctx.fail("'duplicate_as_sensor' is not valid for internal entities")
        # rectify_time is a decode option, so an internal time read-back may carry
        # it; _check_platform_semantics is skipped for internal entities, so the
        # "time only" rule is enforced here on the value type instead.
        if raw.get("rectify_time") is not None and raw.get("type") != "time":
            raise ctx.fail("'rectify_time' is only valid for time entities")
        return "internal", {}

    if not isinstance(ha_raw, dict) or "platform" not in ha_raw:
        raise ctx.fail("'ha:' block with a 'platform:' is required")
    platform = ha_raw["platform"]
    if platform not in PLATFORMS:
        raise ctx.fail(
            f"unknown platform {platform!r}, expected one of {sorted(PLATFORMS)}"
        )
    return platform, _parse_ha(ctx, platform, ha_raw)


def _parse_shape(
    ctx: _Ctx, raw: dict[str, Any], table: str
) -> tuple[str, int, tuple[float, ...] | None, str | None]:
    """Value type, register count, sum_scale weights, and word swap."""
    sum_scale = raw.get("sum_scale")
    if sum_scale is not None:
        if (
            not isinstance(sum_scale, list)
            or not sum_scale
            or any(isinstance(s, bool) or not isinstance(s, (int, float)) for s in sum_scale)
        ):
            raise ctx.fail("sum_scale must be a non-empty list of numbers")
        sum_scale = tuple(float(s) for s in sum_scale)

    if table in BIT_TABLES:
        typ = raw.get("type", "bool")
        if typ != "bool":
            raise ctx.fail(f"type {typ!r} is not valid for a {table} (bit) table")
        for forbidden in ("swap", "sum_scale", "mask", "multiplier", "offset", "map", "flags"):
            if raw.get(forbidden) is not None:
                raise ctx.fail(f"'{forbidden}' is not valid for a {table} (bit) table")
        count = 1
    else:
        typ = raw.get("type", "uint16")
        if isinstance(typ, str):
            typ = TYPE_ALIASES.get(typ, typ)
        if not isinstance(typ, str) or typ == "bool" or (
            typ not in (TYPE_STRING, TYPE_TIME) and typ not in TYPE_BITS
        ):
            raise ctx.fail(
                f"unknown type {typ!r}, expected one of "
                f"{sorted(TYPE_BITS)}, 'string' or 'time'"
            )
        count = _derive_count(ctx, raw, typ, sum_scale)

    swap = raw.get("swap")
    if swap is not None and swap not in SWAP_MODES:
        raise ctx.fail(f"unknown swap {swap!r}, expected one of {sorted(SWAP_MODES)}")
    return typ, count, sum_scale, swap


def _parse_conversions(
    ctx: _Ctx,
    raw: dict[str, Any],
    typ: str,
    count: int,
    sum_scale: tuple[float, ...] | None,
    swap: str | None,
) -> tuple[
    int | None, float | None, float | None, dict[int, str] | None, dict[int, str] | None
]:
    """mask / multiplier / offset / map / flags, plus their combination rules."""
    mask = raw.get("mask")
    if mask is not None:
        if typ in FLOAT_TYPES or typ == TYPE_STRING:
            raise ctx.fail("'mask' requires an integer type")
        mask = _int_in_range(ctx, "mask", mask, 1, (1 << (16 * count)) - 1)

    multiplier = raw.get("multiplier")
    if multiplier is not None:
        multiplier = _number(ctx, "multiplier", multiplier)
        if multiplier == 0:
            raise ctx.fail("multiplier must not be 0")
    offset = raw.get("offset")
    if offset is not None:
        offset = _number(ctx, "offset", offset)

    value_map = _parse_int_str_map(ctx, "map", raw.get("map"))
    flags = _parse_int_str_map(ctx, "flags", raw.get("flags"), max_key=16 * count - 1)

    numeric_conversions = [
        conv for conv in (mask, multiplier, offset, value_map, flags, sum_scale)
        if conv is not None
    ]
    if typ in (TYPE_STRING, TYPE_TIME) and numeric_conversions:
        raise ctx.fail(f"{typ} cannot be combined with numeric conversions")
    if typ in FLOAT_TYPES and (mask is not None or flags is not None):
        raise ctx.fail("floats cannot be combined with mask/flags")
    if value_map and flags:
        raise ctx.fail("'map' and 'flags' are mutually exclusive")
    if (value_map or flags) and (multiplier is not None or offset is not None):
        raise ctx.fail("'map'/'flags' cannot be combined with multiplier/offset")
    return mask, multiplier, offset, value_map, flags


def _derive_count(
    ctx: _Ctx, raw: dict[str, Any], typ: str, sum_scale: tuple[float, ...] | None
) -> int:
    explicit = raw.get("count")
    if explicit is not None:
        explicit = _int_in_range(ctx, "count", explicit, 1, 125)
    if typ == TYPE_STRING:
        if sum_scale:
            raise ctx.fail("sum_scale is not valid for strings")
        if explicit is None:
            raise ctx.fail("strings require 'count' (registers; 2 characters each)")
        return explicit
    if typ == TYPE_TIME:
        if sum_scale:
            raise ctx.fail("sum_scale is not valid for time")
        if explicit is not None and explicit not in (1, 2):
            raise ctx.fail(
                "time occupies one register (packed hour*256+minute) or two "
                "(hour, then minute)"
            )
        return explicit or 1
    if sum_scale is not None:
        derived = (TYPE_BITS[typ] * len(sum_scale) + 15) // 16
        if explicit is not None and explicit != derived:
            raise ctx.fail(
                f"count {explicit} contradicts sum_scale "
                f"({len(sum_scale)} x {typ} needs {derived})"
            )
        return derived
    derived = TYPE_WIDTH[typ]
    if explicit is not None and explicit != derived:
        raise ctx.fail(f"count {explicit} contradicts type {typ} (needs {derived})")
    return derived


def _bool(ctx: _Ctx, raw: dict[str, Any], name: str) -> bool:
    value = raw.get(name, False)
    if not isinstance(value, bool):
        raise ctx.fail(f"'{name}' must be true or false")
    return value


def _on_off(ctx: _Ctx, raw: dict[str, Any], name: str) -> int | bool | None:
    value = raw.get(name)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    raise ctx.fail(f"'{name}' must be an integer or boolean")


def _parse_write_value(ctx: _Ctx, raw: Any) -> Any:
    """A button's press payload. Three forms:

    * a fixed number/bool, or a single Jinja template string — rendered, then written
      through the entity's codec, so it honours ``type``/``map``/``multiplier``/``count``
      (int32, float, mapped labels, strings all work);
    * a list of numbers and template strings — each written as one raw 16-bit register
      to consecutive addresses in a single FC16 transaction (e.g. an RTC sync).
    """
    if raw is None or isinstance(raw, (int, float, bool)):
        return raw
    if isinstance(raw, str):
        if not raw.strip():
            raise ctx.fail("write_value template string must not be empty")
        return raw
    if isinstance(raw, list):
        if not raw:
            raise ctx.fail("write_value list must not be empty")
        items: list[Any] = []
        for item in raw:
            if isinstance(item, bool) or not isinstance(item, (int, float, str)):
                raise ctx.fail("write_value list items must be numbers or template strings")
            if isinstance(item, str) and not item.strip():
                raise ctx.fail("write_value template strings must not be empty")
            items.append(item)
        return tuple(items)
    raise ctx.fail(
        "write_value must be a number, boolean, template string, or a list of those"
    )


def _parse_int_str_map(
    ctx: _Ctx, name: str, raw: Any, max_key: int | None = None
) -> dict[int, str] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict) or not raw:
        raise ctx.fail(f"'{name}' must be a non-empty mapping of integer -> text")
    out: dict[int, str] = {}
    for k, v in raw.items():
        if isinstance(k, bool) or not isinstance(k, int) or k < 0:
            raise ctx.fail(f"'{name}' keys must be non-negative integers, got {k!r}")
        if max_key is not None and k > max_key:
            raise ctx.fail(f"'{name}' key {k} out of range (bit numbers are 0-indexed)")
        out[k] = ctx.localize(str(v))
    return out


@cache
def description_fields(desc_cls: type[EntityDescription]) -> frozenset[str]:
    """Field names of an HA EntityDescription class.

    The classes are not plain dataclasses (FrozenOrThawed metaclass), but
    their generated ``__init__`` carries every field as a parameter.
    """
    params = inspect.signature(desc_cls.__init__).parameters
    return frozenset(params) - {"self", "key"}


def _parse_ha(ctx: _Ctx, platform: str, ha_raw: dict[str, Any]) -> dict[str, Any]:
    desc_cls = DESCRIPTION_CLASSES[platform]
    allowed = description_fields(desc_cls)
    enum_fields = _ENUM_FIELDS.get(platform, {})
    out: dict[str, Any] = {}
    for raw_name, value in ha_raw.items():
        if raw_name == "platform":
            continue
        name = HA_ALIASES.get(raw_name, raw_name)
        if name not in allowed:
            # Only offer aliases whose target field this platform actually has.
            aliases = {a for a, target in HA_ALIASES.items() if target in allowed}
            raise ctx.fail(
                f"ha.{raw_name} is not a {platform} entity field "
                f"(valid: {', '.join(sorted(allowed | aliases))})"
            )
        if name == "entity_category" and isinstance(value, str):
            value = _coerce_enum(ctx, f"ha.{raw_name}", value, EntityCategory)
        elif name in enum_fields and isinstance(value, str):
            value = _coerce_enum(ctx, f"ha.{raw_name}", value, enum_fields[name])
        out[name] = value
    # ``name`` is the only free-text, human-facing EntityDescription field.
    if isinstance(out.get("name"), str):
        out["name"] = ctx.localize(out["name"])
    return out


def _coerce_enum(ctx: _Ctx, name: str, value: str, enum_cls: type) -> Any:
    try:
        return enum_cls(value)
    except ValueError:
        valid = ", ".join(sorted(m.value for m in enum_cls))  # type: ignore[attr-defined]
        raise ctx.fail(f"{name}: {value!r} is invalid (valid: {valid})") from None


def _check_platform_semantics(ctx: _Ctx, defn: EntityDef) -> None:
    _check_write_semantics(ctx, defn)
    _check_value_semantics(ctx, defn)


def _check_write_semantics(ctx: _Ctx, defn: EntityDef) -> None:
    """Writability rules: table, button write_value, select map."""
    platform = defn.platform
    if defn.writes and defn.table not in WRITABLE_TABLES:
        raise ctx.fail(f"platform {platform} writes, but table {defn.table} is read-only")

    if platform == "button":
        if defn.write_value is None:
            raise ctx.fail("buttons require 'write_value'")
    elif defn.write_value is not None:
        raise ctx.fail("'write_value' is only valid for buttons")

    # A list write_value writes consecutive registers via FC16, so it needs a register
    # table, not a coil.
    if isinstance(defn.write_value, tuple) and defn.table in BIT_TABLES:
        raise ctx.fail("a list write_value writes registers (FC16); it can't target a coil")

    # read_register decouples the read side; only meaningful for entities that both
    # write and show a value (number/select/switch/text), not read-only or buttons.
    if defn.read_register is not None and (not defn.writes or platform == "button"):
        raise ctx.fail("'read_register' is only valid on writable, readable platforms")

    # static_value: never-read register, shown from the seed and last write only.
    # optimistic_default: read the register, fall back to the value when it decodes
    # to nothing. Both keep a writable control usable; they cannot combine.
    for name, value in (
        ("static_value", defn.static_value),
        ("optimistic_default", defn.optimistic_default),
    ):
        if value is None:
            continue
        if not defn.writes or platform == "button":
            raise ctx.fail(f"'{name}' is only valid on writable, readable platforms")
        if defn.read_register is not None:
            raise ctx.fail(f"'{name}' and 'read_register' are mutually exclusive")
    if defn.static_value is not None and defn.optimistic_default is not None:
        raise ctx.fail("'static_value' and 'optimistic_default' are mutually exclusive")
    if defn.write_multiple and (not defn.writes or defn.table not in WRITABLE_TABLES):
        raise ctx.fail("'write_multiple' is only valid on writable register platforms")
    if defn.write_multiple and defn.table in BIT_TABLES:
        raise ctx.fail("'write_multiple' applies to register writes, not coils")

    # confirm_delay defers the read-back that follows a write; it needs a write
    # that is actually confirmed from the entity's own register.
    if defn.confirm_delay is not None and (
        not defn.writes
        or platform == "button"
        or defn.read_register is not None
        or defn.static_value is not None
    ):
        raise ctx.fail(
            "'confirm_delay' needs a write confirmed from the entity's own "
            "register (not valid for buttons, read_register, or static_value "
            "entities)"
        )

    # A masked write must merge into the register's other bits, which requires
    # read_modify_write; without it every write would fail at runtime. A button
    # with a list write_value bypasses the codec, so the mask is decode-only there.
    if (
        defn.writes
        and defn.mask is not None
        and not defn.read_modify_write
        and not isinstance(defn.write_value, tuple)
    ):
        raise ctx.fail("writable entities with 'mask' require 'read_modify_write: true'")

    if platform == "select":
        if not defn.value_map:
            raise ctx.fail("selects require 'map' (register value -> option)")
        if len(set(defn.value_map.values())) != len(defn.value_map):
            raise ctx.fail("select 'map' values must be unique")


def _check_value_semantics(ctx: _Ctx, defn: EntityDef) -> None:
    """Value shape rules per platform: types, min/max, on/off, flags."""
    platform = defn.platform
    if platform == "text" and defn.type != TYPE_STRING:
        raise ctx.fail("text entities require type 'string'")

    if platform == "time" and defn.type != TYPE_TIME:
        raise ctx.fail("time entities require type 'time'")
    if defn.type == TYPE_TIME and platform != "time":
        raise ctx.fail("type 'time' is only valid for the time platform")
    if defn.rectify_time and platform != "time":
        raise ctx.fail("'rectify_time' is only valid for time entities")

    if platform == "number":
        if defn.type == TYPE_STRING:
            raise ctx.fail("numbers need a numeric type (use a text entity for strings)")
        for field in ("native_min_value", "native_max_value"):
            if field not in defn.ha:
                raise ctx.fail("numbers require ha.min and ha.max")
        if defn.value_map or defn.flags:
            raise ctx.fail("numbers cannot use map/flags")

    # A valve is either binary (open/close like a switch, the default) or —
    # with ha.reports_position — a 0..100 position control (numeric, no on/off).
    position_valve = platform == "valve" and bool(defn.ha.get("reports_position"))
    if position_valve:
        if defn.table in BIT_TABLES:
            raise ctx.fail("a position valve needs a register, not a coil")
        if defn.on_value is not None or defn.off_value is not None:
            raise ctx.fail(
                "'on_value'/'off_value' are only for binary valves "
                "(remove them or drop ha.reports_position)"
            )
        if defn.type == TYPE_STRING or defn.flags or defn.value_map:
            raise ctx.fail("position valves need a plain numeric value (0-100)")

    if platform in ("switch", "binary_sensor") or (
        platform == "valve" and not position_valve
    ):
        # A 'map' decodes to a label string, which the integer/boolean on/off
        # comparison can never match — the entity would be stuck on.
        if defn.type == TYPE_STRING or defn.flags or defn.value_map:
            raise ctx.fail(
                f"{platform} entities need a plain numeric or bit value (no map/"
                "flags/string; use 'on_value'/'off_value' to pick the raw values)"
            )
    elif not position_valve and (
        defn.on_value is not None or defn.off_value is not None
    ):
        raise ctx.fail(
            "'on_value'/'off_value' are only valid for switch, binary_sensor, "
            "and valve"
        )

    # Reading compares against on_value first; a lone off_value would be used
    # for writing but silently ignored on read (turn-off would show as on).
    if defn.off_value is not None and defn.on_value is None:
        raise ctx.fail("'off_value' requires 'on_value'")

    if defn.flags and platform != "sensor":
        raise ctx.fail("'flags' is only valid for sensors")

    if defn.duplicate_as_sensor and not defn.writes:
        raise ctx.fail("'duplicate_as_sensor' only makes sense for writable platforms")
    if defn.duplicate_as_sensor and defn.platform == "button":
        raise ctx.fail(
            "'duplicate_as_sensor' is not valid for buttons (they never read a value)"
        )

    if defn.writes and platform != "button" and defn.flags is not None:
        raise ctx.fail("flags entities are read-only")


# --- template: section ---------------------------------------------------------
#
# Each template platform is described by a spec: which keys are Jinja
# templates, which are write actions (and of which kind), and which are
# static values handled by a post hook. Action kinds:
#   fixed  - writes a configured 'value' (turn_on, open_cover, ...)
#   value  - writes the value coming from the UI (set_temperature, ...)
#   mapped - writes the UI value, optionally translated by a 'map'


@dataclass(frozen=True)
class _TplSpec:
    req_templates: tuple[str, ...] = ()
    opt_templates: tuple[str, ...] = ()
    req_fixed: tuple[str, ...] = ()
    opt_fixed: tuple[str, ...] = ()
    req_value: tuple[str, ...] = ()
    opt_value: tuple[str, ...] = ()
    req_mapped: tuple[str, ...] = ()
    opt_mapped: tuple[str, ...] = ()
    statics: tuple[str, ...] = ()

    @property
    def allowed(self) -> set[str]:
        return {
            "ha",
            "groups",
            *self.req_templates,
            *self.opt_templates,
            *self.req_fixed,
            *self.opt_fixed,
            *self.req_value,
            *self.opt_value,
            *self.req_mapped,
            *self.opt_mapped,
            *self.statics,
        }


_TEMPLATE_SPECS: dict[str, _TplSpec] = {
    "sensor": _TplSpec(req_templates=("state",), statics=("integrate",)),
    "binary_sensor": _TplSpec(req_templates=("state",)),
    "switch": _TplSpec(req_templates=("state",), req_fixed=("turn_on", "turn_off")),
    "number": _TplSpec(req_templates=("state",), req_value=("set_value",)),
    "select": _TplSpec(
        req_templates=("state",), req_mapped=("select_option",), statics=("options",)
    ),
    "light": _TplSpec(
        req_templates=("state",),
        opt_templates=("brightness",),
        req_fixed=("turn_on", "turn_off"),
        opt_value=("set_brightness",),
    ),
    "fan": _TplSpec(
        req_templates=("state",),
        opt_templates=("percentage", "preset_mode"),
        req_fixed=("turn_on", "turn_off"),
        opt_value=("set_percentage",),
        opt_mapped=("set_preset_mode",),
        statics=("preset_modes",),
    ),
    "cover": _TplSpec(
        opt_templates=("is_closed", "position"),
        opt_fixed=("open_cover", "close_cover", "stop_cover"),
        opt_value=("set_position",),
    ),
    "climate": _TplSpec(
        opt_templates=(
            "current_temperature",
            "target_temperature",
            "hvac_mode",
            "hvac_action",
        ),
        opt_value=("set_temperature",),
        opt_mapped=("set_hvac_mode",),
        statics=("min_temp", "max_temp", "temp_step", "temperature_unit", "hvac_modes"),
    ),
}


def _parse_template(
    ctx: _Ctx, key: str, raw: Any, defs: dict[str, EntityDef]
) -> TemplateDef:
    if not isinstance(raw, dict):
        raise ctx.fail("template entry must be a mapping")
    ha_raw = raw.get("ha")
    if not isinstance(ha_raw, dict) or "platform" not in ha_raw:
        raise ctx.fail("'ha:' block with a 'platform:' is required")
    platform = ha_raw["platform"]
    if platform not in TEMPLATE_PLATFORMS:
        raise ctx.fail(f"template platform must be one of {sorted(TEMPLATE_PLATFORMS)}")

    spec = _TEMPLATE_SPECS[platform]
    unknown = set(raw) - spec.allowed
    if unknown:
        raise ctx.fail(
            f"unknown {platform} template keys: {sorted(unknown)} "
            f"(valid: {sorted(spec.allowed - {'ha'})})"
        )

    config: dict[str, Any] = {}
    _collect_template_strings(ctx, spec, raw, config)
    _collect_template_actions(ctx, spec, raw, defs, config, platform)

    ha = _parse_ha(ctx, platform, ha_raw)
    post = _TEMPLATE_POST.get(platform)
    if post:
        post(ctx, raw, config, defs, ha)

    groups = _parse_groups(ctx, "groups", raw.get("groups"))
    return TemplateDef(key=key, platform=platform, ha=ha, config=config, groups=groups)


def _collect_template_strings(
    ctx: _Ctx, spec: _TplSpec, raw: dict[str, Any], config: dict[str, Any]
) -> None:
    """Validate and collect the Jinja template fields of a template entry."""
    for name in (*spec.req_templates, *spec.opt_templates):
        if name in raw:
            if not isinstance(raw[name], str):
                raise ctx.fail(f"'{name}' must be a template string")
            config[name] = raw[name]
        elif name in spec.req_templates:
            raise ctx.fail(f"'{name}' (a template string) is required")


def _collect_template_actions(
    ctx: _Ctx,
    spec: _TplSpec,
    raw: dict[str, Any],
    defs: dict[str, EntityDef],
    config: dict[str, Any],
    platform: str,
) -> None:
    """Validate and collect the write actions of a template entry."""
    for kind, names in (
        ("fixed", (*spec.req_fixed, *spec.opt_fixed)),
        ("value", (*spec.req_value, *spec.opt_value)),
        ("mapped", (*spec.req_mapped, *spec.opt_mapped)),
    ):
        required = getattr(spec, f"req_{kind}")
        for name in names:
            if name in raw:
                config[name] = _parse_write_target(ctx, name, raw[name], defs, kind)
            elif name in required:
                raise ctx.fail(f"'{name}' action is required for {platform} templates")


def _parse_write_target(
    ctx: _Ctx, name: str, raw: Any, defs: dict[str, EntityDef], kind: str
) -> WriteTarget | SwitchTarget:
    """A single target, or a ``by``/``cases`` switch picking one at write time."""
    if isinstance(raw, dict) and ("by" in raw or "cases" in raw):
        return _parse_switch_target(ctx, name, raw, defs, kind)
    return _parse_single_target(ctx, name, raw, defs, kind)


def _parse_switch_target(
    ctx: _Ctx, name: str, raw: dict[str, Any], defs: dict[str, EntityDef], kind: str
) -> SwitchTarget:
    unknown = set(raw) - {"by", "cases"}
    if unknown:
        raise ctx.fail(f"'{name}': unknown keys {sorted(unknown)} (valid: ['by', 'cases'])")
    selector = raw.get("by")
    if not isinstance(selector, str):
        raise ctx.fail(f"'{name}.by' must be a template string selecting a case")
    cases_raw = raw.get("cases")
    if not isinstance(cases_raw, dict) or not cases_raw:
        raise ctx.fail(f"'{name}.cases' must be a non-empty mapping of value -> target")
    # Same YAML 1.1 footgun as entity on/off keys: an unquoted on/off/yes/no
    # case key parses as a boolean and would silently become "True"/"False".
    if any(isinstance(k, bool) for k in cases_raw):
        raise ctx.fail(
            f"'{name}.cases': unquoted on/off/yes/no/true/false keys are YAML "
            'booleans — quote them (e.g. "off":)'
        )
    cases = {
        str(key): _parse_single_target(ctx, f"{name}.cases.{key}", target, defs, kind)
        for key, target in cases_raw.items()
    }
    return SwitchTarget(selector=selector, cases=cases)


def _parse_single_target(
    ctx: _Ctx, name: str, raw: Any, defs: dict[str, EntityDef], kind: str
) -> WriteTarget:
    if not isinstance(raw, dict) or "entity" not in raw:
        raise ctx.fail(f"'{name}' must be a mapping with an 'entity' key")
    allowed = {"entity"} | ({"value"} if kind == "fixed" else set())
    allowed |= {"map"} if kind == "mapped" else set()
    unknown = set(raw) - allowed
    if unknown:
        raise ctx.fail(f"'{name}': unknown keys {sorted(unknown)} (valid: {sorted(allowed)})")

    target = str(raw["entity"])
    defn = defs.get(target)
    if defn is None:
        raise ctx.fail(f"'{name}.entity' references unknown entity '{target}'")
    if defn.table not in WRITABLE_TABLES:
        raise ctx.fail(
            f"'{name}.entity' targets '{target}' in the read-only '{defn.table}:' section"
        )
    _check_target_encodable(ctx, name, target, defn)

    value = raw.get("value")
    if kind == "fixed":
        if value is None or not isinstance(value, (int, float, bool, str)):
            raise ctx.fail(
                f"'{name}' needs a 'value' (a number, boolean, or map label) to write"
            )
        if isinstance(value, str):
            # A string payload is an option label of the (possibly translated)
            # target entity, so it localizes in lockstep with the target's map.
            value = ctx.localize(value)
        _check_payload(ctx, f"{name}.value", value, target, defn)

    value_map = raw.get("map")
    if value_map is not None:
        if not isinstance(value_map, dict) or not value_map:
            raise ctx.fail(f"'{name}.map' must be a non-empty mapping")
        # Same YAML 1.1 footgun as entity on/off keys: an unquoted on/off/yes/no
        # key parses as a boolean and would silently become "True"/"False".
        if any(isinstance(k, bool) for k in value_map):
            raise ctx.fail(
                f"'{name}.map': unquoted on/off/yes/no/true/false keys are YAML "
                'booleans — quote them (e.g. "off":)'
            )
        # A string payload is an option label of the (possibly translated) target
        # entity, so localize it in lockstep; numbers/bools are written as-is.
        value_map = {
            str(k): ctx.localize(v) if isinstance(v, str) else v
            for k, v in value_map.items()
        }
        for map_key, payload in value_map.items():
            _check_payload(ctx, f"{name}.map[{map_key!r}]", payload, target, defn)
    elif kind == "value" and defn.value_map is not None:
        raise ctx.fail(
            f"'{name}' writes the UI value (a number) to '{target}', which has a "
            "'map' and accepts only its labels"
        )
    return WriteTarget(entity=target, value=value, value_map=value_map)


def _check_target_encodable(ctx: _Ctx, name: str, target: str, defn: EntityDef) -> None:
    """Reject write targets no action payload could ever encode for."""
    if defn.platform == "button":
        raise ctx.fail(
            f"'{name}.entity' targets the button '{target}'; target its register "
            "with a separate (e.g. internal) entity instead"
        )
    if defn.type == TYPE_TIME:
        raise ctx.fail(
            f"'{name}.entity' targets the time entity '{target}', which only "
            "accepts a time-of-day (no action payload produces one)"
        )
    if defn.flags is not None:
        raise ctx.fail(f"'{name}.entity' targets '{target}', but flags entities are read-only")
    if defn.mask is not None and not defn.read_modify_write:
        raise ctx.fail(
            f"'{name}.entity' targets '{target}', whose masked write needs "
            "'read_modify_write: true'"
        )


def _check_payload(ctx: _Ctx, where: str, payload: Any, target: str, defn: EntityDef) -> None:
    """A concrete action payload must be encodable for the target entity."""
    if defn.value_map is not None:
        # The codec unmaps a label back to the register value; anything else
        # (including the raw register number) raises on every single write.
        if not isinstance(payload, str) or payload not in set(defn.value_map.values()):
            raise ctx.fail(
                f"'{where}': {payload!r} is not one of the map labels of '{target}' "
                f"({sorted(defn.value_map.values())})"
            )
        return
    if isinstance(payload, str):
        if defn.table in BIT_TABLES:
            raise ctx.fail(f"'{where}': a coil write needs a boolean or number, not {payload!r}")
        if defn.type != TYPE_STRING:
            raise ctx.fail(f"'{where}': {payload!r} is a string, but '{target}' expects a number")


# --- per-platform statics and consistency ------------------------------------------


def _str_list(ctx: _Ctx, name: str, raw: Any) -> list[str]:
    if not isinstance(raw, list) or not raw:
        raise ctx.fail(f"'{name}' must be a non-empty list")
    return [str(v) for v in raw]


def _post_climate(
    ctx: _Ctx,
    raw: dict[str, Any],
    config: dict[str, Any],
    defs: dict[str, EntityDef],
    ha: dict[str, Any],
) -> None:
    for name in ("min_temp", "max_temp", "temp_step"):
        if name in raw:
            config[name] = _number(ctx, name, raw[name])
    if "temperature_unit" in raw:
        config["temperature_unit"] = str(
            _coerce_enum(
                ctx, "temperature_unit", str(raw["temperature_unit"]), UnitOfTemperature
            )
        )
    modes = raw.get("hvac_modes")
    if modes is None and (vmap := getattr(config.get("set_hvac_mode"), "value_map", None)):
        modes = list(vmap)
    if modes is not None:
        config["hvac_modes"] = [
            str(_coerce_enum(ctx, "hvac_modes", str(m).lower(), HVACMode))
            for m in _str_list(ctx, "hvac_modes", modes)
        ]
    if "set_hvac_mode" in config and "hvac_modes" not in config:
        raise ctx.fail("'set_hvac_mode' needs 'hvac_modes' (or a 'map' to derive them from)")


def _post_select(
    ctx: _Ctx,
    raw: dict[str, Any],
    config: dict[str, Any],
    defs: dict[str, EntityDef],
    ha: dict[str, Any],
) -> None:
    target = config["select_option"]
    target_map = getattr(target, "value_map", None)
    target_entity = getattr(target, "entity", None)
    if "options" in raw:
        # Explicit options are the UI values select_option writes (through the
        # target's map when it has one), so they localize and validate exactly
        # like fixed payloads — otherwise a translated file's state (localized
        # label) could never match its options, and an unwritable option would
        # fail on every select.
        options = [ctx.localize(o) for o in _str_list(ctx, "options", raw["options"])]
        if target_map is None:
            targets = (
                list(target.cases.values())
                if isinstance(target, SwitchTarget)
                else [target]
            )
            for tgt in targets:
                if tgt.value_map is not None:
                    continue  # the per-case map translates the option instead
                for option in options:
                    _check_payload(
                        ctx, f"options[{option!r}]", option, tgt.entity, defs[tgt.entity]
                    )
    elif target_map:
        options = list(target_map)
    elif target_entity and (entity_map := defs[target_entity].value_map):
        options = list(entity_map.values())
    else:
        raise ctx.fail(
            "cannot determine the options: provide 'options', a 'map' on "
            "select_option, or target an entity that has a 'map'"
        )
    config["options"] = options


def _post_fan(
    ctx: _Ctx,
    raw: dict[str, Any],
    config: dict[str, Any],
    defs: dict[str, EntityDef],
    ha: dict[str, Any],
) -> None:
    presets = raw.get("preset_modes")
    if presets is None and (vmap := getattr(config.get("set_preset_mode"), "value_map", None)):
        presets = list(vmap)
    if presets is not None:
        config["preset_modes"] = _str_list(ctx, "preset_modes", presets)
    if ("preset_mode" in config or "set_preset_mode" in config) and "preset_modes" not in config:
        raise ctx.fail(
            "fan presets need 'preset_modes' (or a 'map' on set_preset_mode)"
        )


def _post_cover(
    ctx: _Ctx,
    raw: dict[str, Any],
    config: dict[str, Any],
    defs: dict[str, EntityDef],
    ha: dict[str, Any],
) -> None:
    if "is_closed" not in config and "position" not in config:
        raise ctx.fail("covers need an 'is_closed' or 'position' template")


def _post_number(
    ctx: _Ctx,
    raw: dict[str, Any],
    config: dict[str, Any],
    defs: dict[str, EntityDef],
    ha: dict[str, Any],
) -> None:
    for field in ("native_min_value", "native_max_value"):
        if field not in ha:
            raise ctx.fail("template numbers require ha.min and ha.max")


INTEGRATE_METHODS = ("trapezoidal", "left", "right")


def _post_sensor(
    ctx: _Ctx,
    raw: dict[str, Any],
    config: dict[str, Any],
    defs: dict[str, EntityDef],
    ha: dict[str, Any],
) -> None:
    """``integrate``: the state template yields watts; the sensor accumulates
    kilowatt-hours over time with the given Riemann-sum method."""
    method = raw.get("integrate")
    if method is None:
        return
    if method not in INTEGRATE_METHODS:
        raise ctx.fail(f"'integrate' must be one of {sorted(INTEGRATE_METHODS)}")
    config["integrate"] = method


_TEMPLATE_POST = {
    "climate": _post_climate,
    "select": _post_select,
    "fan": _post_fan,
    "cover": _post_cover,
    "number": _post_number,
    "sensor": _post_sensor,
}
