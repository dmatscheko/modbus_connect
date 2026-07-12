#!/usr/bin/env python3
"""Generate docs/device_files.schema.json from the integration's own rules.

The JSON Schema gives device-file authors autocomplete and inline validation
in any editor with a YAML language server (VS Code: the YAML extension), via
this first line in a device file:

  # yaml-language-server: $schema=https://raw.githubusercontent.com/dmatscheko/modbus_connect/main/docs/device_files.schema.json

It is generated, not hand-written: the per-platform ``ha:`` fields come from
the same Home Assistant ``EntityDescription`` introspection the integration
validates with at load time (schema.py), so a new HA release regenerates into
new editor suggestions. Editor validation is a best-effort typo net — the
integration's load-time validation stays authoritative for cross-field rules
(internal entities, writability, conversion combinations, ...).

Run from the repo root:  .venv/bin/python support/build_json_schema.py
The freshness test (tests/test_json_schema.py) fails when the committed file
is stale, and validates every bundled device file against the result.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from homeassistant.helpers.entity import EntityCategory  # noqa: E402

from custom_components.modbus_connect.models import (  # noqa: E402
    PLATFORMS,
    SWAP_MODES,
    TABLES,
    TYPE_ALIASES,
    TYPE_BITS,
    TYPE_STRING,
    TYPE_TIME,
)
from custom_components.modbus_connect.schema import (  # noqa: E402
    _ENUM_FIELDS,
    _TEMPLATE_SPECS,
    DESCRIPTION_CLASSES,
    HA_ALIASES,
    INTEGRATE_METHODS,
    description_fields,
)

OUT_PATH = REPO / "docs" / "device_files.schema.json"

SCHEMA_ID = (
    "https://raw.githubusercontent.com/dmatscheko/modbus_connect/main/"
    "docs/device_files.schema.json"
)

STRING = {"type": "string"}
NUMBER = {"type": "number"}
INTEGER = {"type": "integer"}
BOOLEAN = {"type": "boolean"}
GROUPS = {"type": "array", "items": STRING, "minItems": 1}
# YAML integer keys reach the language server stringified
INT_KEYED_MAP = {
    "type": "object",
    "patternProperties": {"^[0-9]+$": {"type": ["string", "number", "boolean"]}},
    "additionalProperties": False,
    "minProperties": 1,
}

# EntityDescription fields with a known JSON shape; anything not listed (or an
# enum from _ENUM_FIELDS) stays unconstrained so new HA fields never get
# rejected by a stale schema.
FIELD_TYPES: dict[str, dict[str, Any]] = {
    "name": STRING,
    "icon": STRING,
    "translation_key": STRING,
    "translation_placeholders": {"type": "object"},
    "native_unit_of_measurement": STRING,
    "unit_of_measurement": STRING,
    "suggested_unit_of_measurement": STRING,
    "native_min_value": NUMBER,
    "native_max_value": NUMBER,
    "native_step": NUMBER,
    "native_precision": INTEGER,
    "suggested_display_precision": INTEGER,
    "native_max": INTEGER,
    "native_min": INTEGER,
    "pattern": STRING,
    "options": {"type": "array", "items": STRING},
    "entity_registry_enabled_default": BOOLEAN,
    "entity_registry_visible_default": BOOLEAN,
    "force_update": BOOLEAN,
    "assumed_state": BOOLEAN,
    "has_entity_name": BOOLEAN,
    "entity_category": {"enum": sorted(m.value for m in EntityCategory)},
}

MODBUS_TYPES = sorted({*TYPE_BITS, *TYPE_ALIASES, TYPE_STRING, TYPE_TIME})

# The template statics with a fixed shape (see schema.py _TEMPLATE_POST hooks)
STATIC_TYPES: dict[str, dict[str, Any]] = {
    "options": {"type": "array", "items": STRING},
    "preset_modes": {"type": "array", "items": STRING},
    "hvac_modes": {"type": "array", "items": STRING},
    "min_temp": NUMBER,
    "max_temp": NUMBER,
    "temp_step": NUMBER,
    "temperature_unit": STRING,
    "integrate": {"enum": sorted(INTEGRATE_METHODS)},
}


def _ha_field_schema(platform: str, field: str) -> dict[str, Any]:
    enum_cls = _ENUM_FIELDS.get(platform, {}).get(field)
    if enum_cls is not None:
        return {"enum": sorted(m.value for m in enum_cls)}
    return FIELD_TYPES.get(field, {})


def _ha_properties(platform: str) -> dict[str, Any]:
    """The ha: block properties for one platform: real fields plus aliases."""
    fields = description_fields(DESCRIPTION_CLASSES[platform])
    props: dict[str, Any] = {"platform": {"const": platform}}
    for field in sorted(fields):
        props[field] = _ha_field_schema(platform, field)
    for alias, target in sorted(HA_ALIASES.items()):
        if target in fields:
            props[alias] = _ha_field_schema(platform, target)
    return props


def _ha_block(platforms: list[str]) -> dict[str, Any]:
    """An ha: block schema: platform enum plus per-platform field variants."""
    variants = [
        {
            "if": {
                "required": ["platform"],
                "properties": {"platform": {"const": platform}},
            },
            "then": {
                "properties": _ha_properties(platform),
                "additionalProperties": False,
            },
        }
        for platform in platforms
    ]
    return {
        "type": "object",
        "required": ["platform"],
        "properties": {"platform": {"enum": platforms}},
        "allOf": variants,
    }


def _action(kind: str) -> dict[str, Any]:
    """A template write action: a single target, or a by/cases switch."""
    props: dict[str, Any] = {"entity": STRING}
    required = ["entity"]
    if kind == "fixed":
        props["value"] = {"type": ["number", "boolean"]}
        required.append("value")
    if kind == "mapped":
        props["map"] = {"type": "object", "minProperties": 1}
    single = {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }
    switch = {
        "type": "object",
        "properties": {
            "by": STRING,
            "cases": {
                "type": "object",
                "additionalProperties": single,
                "minProperties": 1,
            },
        },
        "required": ["by", "cases"],
        "additionalProperties": False,
    }
    return {"anyOf": [single, switch]}


def _template_entry() -> dict[str, Any]:
    """One template: entry — per-platform keys via if/then on ha.platform."""
    variants = []
    for platform, spec in sorted(_TEMPLATE_SPECS.items()):
        props: dict[str, Any] = {
            "ha": {"$ref": "#/definitions/template_ha"},
            "groups": GROUPS,
        }
        for name in (*spec.req_templates, *spec.opt_templates):
            props[name] = STRING
        for kind in ("fixed", "value", "mapped"):
            for name in (*getattr(spec, f"req_{kind}"), *getattr(spec, f"opt_{kind}")):
                props[name] = {"$ref": f"#/definitions/action_{kind}"}
        for name in spec.statics:
            props[name] = STATIC_TYPES.get(name, {})
        required = [
            "ha",
            *spec.req_templates,
            *spec.req_fixed,
            *spec.req_value,
            *spec.req_mapped,
        ]
        variants.append(
            {
                "if": {
                    "required": ["ha"],
                    "properties": {
                        "ha": {
                            "required": ["platform"],
                            "properties": {"platform": {"const": platform}},
                        }
                    },
                },
                "then": {
                    "properties": props,
                    "required": required,
                    "additionalProperties": False,
                },
            }
        )
    return {"type": "object", "required": ["ha"], "allOf": variants}


def _entity(bit_table: bool) -> dict[str, Any]:
    """One entity of a table section (bit tables forbid the word conversions)."""
    props: dict[str, Any] = {
        "address": {"type": "integer", "minimum": 0, "maximum": 0xFFFF},
        "internal": BOOLEAN,
        "on_value": {"type": ["integer", "boolean"]},
        "off_value": {"type": ["integer", "boolean"]},
        "write_value": {
            "type": ["number", "boolean", "string", "array"],
            "items": {"type": ["number", "string"]},
        },
        "read_register": STRING,
        "static_value": {"type": ["number", "boolean", "string"]},
        "optimistic_default": {"type": ["number", "boolean", "string"]},
        "write_multiple": BOOLEAN,
        "confirm_delay": {"type": "number", "exclusiveMinimum": 0, "maximum": 10},
        "read_modify_write": BOOLEAN,
        "max_change": {"type": "number", "minimum": 0},
        "never_resets": BOOLEAN,
        "scan_interval": {"type": "integer", "minimum": 1, "maximum": 86400},
        "duplicate_as_sensor": BOOLEAN,
        "groups": GROUPS,
        "ha": {"$ref": "#/definitions/entity_ha"},
    }
    if not bit_table:
        props.update(
            {
                "type": {"enum": MODBUS_TYPES},
                "count": {"type": "integer", "minimum": 1, "maximum": 125},
                "swap": {"enum": sorted(SWAP_MODES)},
                "sum_scale": {"type": "array", "items": NUMBER, "minItems": 1},
                "mask": {"type": "integer", "minimum": 1},
                "multiplier": NUMBER,
                "offset": NUMBER,
                "map": INT_KEYED_MAP,
                "flags": INT_KEYED_MAP,
                "rectify_time": BOOLEAN,
            }
        )
    return {
        "type": "object",
        "required": ["address"],
        "properties": props,
        "additionalProperties": False,
    }


def _address_hints() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            section: {"type": "array", "items": INTEGER, "minItems": 1}
            for section in TABLES
        },
        "additionalProperties": False,
        "minProperties": 1,
    }


def _device_block() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["manufacturer", "model"],
        "properties": {
            "manufacturer": STRING,
            "model": STRING,
            "max_register_read": {"type": "integer", "minimum": 1, "maximum": 2000},
            "max_read_gap": {"type": "integer", "minimum": 0, "maximum": 1000},
            "bad_addresses": _address_hints(),
            "split_before": _address_hints(),
            "scan_interval": {"type": "integer", "minimum": 1, "maximum": 86400},
            "min_scan_interval": {"type": "integer", "minimum": 1, "maximum": 86400},
            "timeout": {"type": "number", "exclusiveMinimum": 0, "maximum": 60},
            "retries": {"type": "integer", "minimum": 0, "maximum": 10},
            "request_delay": {"type": "number", "minimum": 0, "maximum": 5},
            "modbus_id": {"type": "integer", "minimum": 0, "maximum": 255},
            "prefix": {"type": "string", "minLength": 1},
            "sw_version": STRING,
            "hw_version": STRING,
            "serial_number": STRING,
            "default_groups": GROUPS,
            "group_labels": {
                "type": "object",
                "additionalProperties": STRING,
                "minProperties": 1,
            },
        },
        "additionalProperties": False,
    }


def _translations_block() -> dict[str, Any]:
    """The optional top-level translations: catalog.

    Source string -> {language code: text}; both levels non-empty. Used to
    localize human-facing strings (device model, group labels, entity names,
    map/flag values) that appear verbatim elsewhere in the file.
    """
    return {
        "type": "object",
        "additionalProperties": {
            "type": "object",
            "additionalProperties": STRING,
            "minProperties": 1,
        },
        "minProperties": 1,
    }


def build() -> dict[str, Any]:
    word_section = {
        "type": "object",
        "additionalProperties": {"$ref": "#/definitions/word_entity"},
    }
    bit_section = {
        "type": "object",
        "additionalProperties": {"$ref": "#/definitions/bit_entity"},
    }
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": SCHEMA_ID,
        "title": "Modbus Connect device file",
        "description": (
            "Editor-side validation for Modbus Connect device YAML files. "
            "Cross-field rules (internal entities, writability, conversion "
            "combinations, ...) are enforced by the integration on load. "
            "Generated by support/build_json_schema.py — do not edit."
        ),
        "type": "object",
        "required": ["device"],
        "properties": {
            "translations": _translations_block(),
            "device": _device_block(),
            "holding": word_section,
            "input": word_section,
            "coil": bit_section,
            "discrete": bit_section,
            "template": {
                "type": "object",
                "additionalProperties": {"$ref": "#/definitions/template_entry"},
            },
        },
        "additionalProperties": False,
        "definitions": {
            "word_entity": _entity(bit_table=False),
            "bit_entity": _entity(bit_table=True),
            "entity_ha": _ha_block(sorted(PLATFORMS)),
            "template_ha": _ha_block(sorted(_TEMPLATE_SPECS)),
            "template_entry": _template_entry(),
            "action_fixed": _action("fixed"),
            "action_value": _action("value"),
            "action_mapped": _action("mapped"),
        },
    }


def render() -> str:
    return json.dumps(build(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUT_PATH.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(REPO)}")
