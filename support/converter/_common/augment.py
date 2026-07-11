#!/usr/bin/env python3
"""Common augmentation library — the single writer of the bundled device configs.

Every converter (SolaX / modbus_local_gateway / Dimplex-Pichler) builds a *tagged
intermediate* in memory and hands it to :func:`write_augmented`, which is the only
code in the repo that emits a ``device_configs/*.yaml`` file. Because all devices
flow through this one function, every bundled file comes out in the same canonical
style.

Pipeline (nothing is written to disk except the final config):

    intermediate  --load(<device>/augment.yaml)-->  spec        # declarative policy
    intermediate  --apply(spec)-->                   final       # ordered ops
    final         --emit(header)-->                  text        # canonical YAML, _tags stripped
    text          --validate-->                      parse_device round-trip
    write custom_components/modbus_connect/device_configs/<device>.yaml

The intermediate is a plain dict:

    {
      "device":   {...},                              # manufacturer/model/default_groups/...
      "holding"|"input"|"coil"|"discrete": [entity],  # ordered register entities
      "template": [entity],                           # composite HA entities
    }
    entity = {"key": str, "_tags": set[str], "address": int, "ha": {...}, "groups": [...], ...}

``_tags`` and any other ``_``-prefixed key are converter-internal *facts* used for
attribution; they never reach the file (schema.py rejects unknown entity keys). The
*policy* — what to add / remove / patch / group, matched against those tags — lives
in ``support/converter/<device>/augment.yaml``. See the module ``README``/DSL below.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# support/converter/_common/augment.py  ->  parents: _common, converter, support, <repo>
_CONVERTER_DIR = Path(__file__).resolve().parents[1]
_DEST_DIR = Path(__file__).resolve().parents[2].parent / "custom_components/modbus_connect/device_configs"

TABLES = ("holding", "input", "coil", "discrete")
SECTIONS = (*TABLES, "template")

# Canonical per-entity field order: every scalar/list key in schema._MODBUS_KEYS
# except the blocks handled separately (map/flags/read_register/internal/ha).
ENTITY_FIELD_ORDER = (
    "address", "type", "count", "swap", "mask", "sum_scale", "multiplier", "offset",
    "on_value", "off_value", "write_value", "static_value", "optimistic_default",
    "write_multiple", "read_modify_write", "confirm_delay", "rectify_time",
    "max_change", "never_resets", "scan_interval", "duplicate_as_sensor", "groups",
)
_KNOWN_ENTITY_KEYS = {*ENTITY_FIELD_ORDER, "map", "flags", "read_register", "internal", "ha", "key"}

# Canonical order for the keys inside an ``ha:`` block, so the emitted file does not
# depend on the (converter-specific) order the dict happened to be built in. Unknown
# keys keep their original relative order after these.
HA_FIELD_ORDER = (
    "platform", "name", "min", "max", "step", "mode", "unit_of_measurement",
    "device_class", "state_class", "precision", "suggested_display_precision",
    "icon", "entity_category", "enabled_by_default",
)
_HA_INDEX = {name: i for i, name in enumerate(HA_FIELD_ORDER)}


def _ordered_ha_items(ha: dict):
    """``ha`` items in canonical field order (stable for unknown keys)."""
    return sorted(ha.items(), key=lambda kv: _HA_INDEX.get(kv[0], len(HA_FIELD_ORDER)))

# Self-documenting divider written above each section (ported from the MLG converter).
SECTION_COMMENTS = {
    "device": "Device metadata: manufacturer and model, plus optional read/poll tuning.",
    "holding": "Holding registers: 16-bit words, read/write (Modbus FC03 read, FC06/FC16 write).",
    "input": "Input registers: 16-bit words, read-only (Modbus FC04 read).",
    "discrete": "Discrete inputs: single-bit booleans, read-only (Modbus FC02 read).",
    "coil": "Coils: single-bit booleans, read/write (Modbus FC01 read, FC05 write).",
    "template": "Templates: composite Home Assistant entities derived from the registers above.",
}


# --------------------------------------------------------------------------- #
# model helpers (used by converters and tests)
# --------------------------------------------------------------------------- #
def intermediate(device: dict | None = None) -> dict:
    """A fresh, empty tagged intermediate."""
    ir = {"device": dict(device or {})}
    for section in SECTIONS:
        ir[section] = []
    return ir


def add_entity(ir: dict, table: str, key: str, *, tags=(), **fields) -> dict:
    """Append one tagged entity to ``table`` and return it."""
    entity = {"key": key, "_tags": set(tags), **fields}
    ir.setdefault(table, []).append(entity)
    return entity


def _iter(ir: dict):
    """Yield ``(section, entity)`` for every entity across all sections."""
    for section in SECTIONS:
        for entity in ir.get(section, []):
            yield section, entity


# --------------------------------------------------------------------------- #
# apply: run the declarative augment.yaml ops against the intermediate
# --------------------------------------------------------------------------- #
def apply(ir: dict, spec: dict | None) -> dict:
    """Apply an augment spec (``{device, ops}``) to the intermediate, in place.

    ``spec`` is ``None`` for a device with no ``augment.yaml`` — then this is a
    pure strip-only pass (emit still drops ``_tags``)."""
    if not spec:
        return ir
    if spec.get("device"):
        _deep_merge(ir.setdefault("device", {}), spec["device"])
    for op in spec.get("ops", []) or []:
        _apply_op(ir, op)
    return ir


def _apply_op(ir: dict, op: dict) -> None:
    if "add" in op:
        new = dict(op["add"])
        table = new.pop("table", None)
        after = new.pop("after", None)
        before = new.pop("before", None)
        if table not in SECTIONS:
            raise ValueError(f"add: missing/invalid table {table!r} (one of {SECTIONS})")
        if "key" not in new:
            raise ValueError(f"add: entity needs a key ({new!r})")
        new["_tags"] = set(new.get("_tags", ()))
        section = ir.setdefault(table, [])
        # Optional positioning: `after`/`before` name an existing key in the same
        # table so a curated entity lands where it belongs (not just at the end).
        anchor = after if after is not None else before
        index = len(section)
        if anchor is not None:
            pos = next((i for i, e in enumerate(section) if e.get("key") == anchor), None)
            if pos is None:
                raise ValueError(f"add: anchor {anchor!r} not found in {table!r} (adding {new['key']!r})")
            index = pos + 1 if after is not None else pos
        section.insert(index, new)
        return

    where = op.get("where")
    # tolerate the nested form `{remove: {where: {...}}}` (as written in the DSL docs)
    # so a mislaid `where` never silently degrades into "match everything".
    if where is None and isinstance(op.get("remove"), dict):
        where = op["remove"].get("where")
    matched = [(s, e) for s, e in _iter(ir) if _match(s, e, where)]

    if "remove" in op:
        for section, entity in matched:
            ir[section].remove(entity)
    elif "group" in op:
        groups = op["group"] if isinstance(op["group"], list) else [op["group"]]
        for _s, entity in matched:
            _add_groups(entity, groups)
    elif "set" in op:
        for _s, entity in matched:
            _deep_merge(entity, op["set"])
    elif "unset" in op:
        paths = op["unset"] if isinstance(op["unset"], list) else [op["unset"]]
        for _s, entity in matched:
            for path in paths:
                _unset(entity, path)
    elif "tag" in op:
        add = op["tag"] if isinstance(op["tag"], list) else [op["tag"]]
        for _s, entity in matched:
            entity.setdefault("_tags", set()).update(add)
    elif "untag" in op:
        rm = op["untag"] if isinstance(op["untag"], list) else [op["untag"]]
        for _s, entity in matched:
            entity.get("_tags", set()).difference_update(rm)
    else:
        raise ValueError(f"augment op has no known verb (add/remove/set/unset/group/tag/untag): {op!r}")


def _add_groups(entity: dict, groups: list) -> None:
    current = list(entity.get("groups") or [])
    for group in groups:
        if group not in current:
            current.append(group)
    entity["groups"] = current


def _deep_merge(dst: dict, src: dict) -> dict:
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _deep_merge(dst[key], value)
        else:
            dst[key] = value
    return dst


def _unset(entity: dict, path: str) -> None:
    parts = path.split(".")
    node = entity
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node:
            return
        node = node[part]
    if isinstance(node, dict):
        node.pop(parts[-1], None)


# --------------------------------------------------------------------------- #
# where: the entity match predicate (all clauses AND together)
# --------------------------------------------------------------------------- #
def _tags(entity: dict) -> set[str]:
    return entity.get("_tags") or set()


def _raw_name(entity: dict) -> str:
    for tag in _tags(entity):
        if tag.startswith("raw-name:"):
            return tag[len("raw-name:"):]
    return (entity.get("ha") or {}).get("name") or ""


def _as_list(value) -> list:
    return value if isinstance(value, list) else [value]


def _match(section: str, entity: dict, where: dict | None) -> bool:
    if not where:
        return True
    tags = _tags(entity)
    key = entity.get("key", "")
    for clause, value in where.items():
        if clause == "key":
            if key not in _as_list(value):
                return False
        elif clause == "not_key":
            if key in _as_list(value):
                return False
        elif clause == "key_matches":
            if not re.search(value, key):
                return False
        elif clause == "tag":
            if value not in tags:
                return False
        elif clause == "tag_any":
            if not (set(_as_list(value)) & tags):
                return False
        elif clause == "tag_all":
            if not set(_as_list(value)) <= tags:
                return False
        elif clause == "not_tag":
            if set(_as_list(value)) & tags:
                return False
        elif clause == "tag_prefix":
            if not any(t.startswith(p) for p in _as_list(value) for t in tags):
                return False
        elif clause == "tag_matches":
            if not any(re.search(value, t) for t in tags):
                return False
        elif clause == "raw_name_matches":
            if not re.search(value, _raw_name(entity), re.I):
                return False
        elif clause == "table":
            if section not in _as_list(value):
                return False
        elif clause == "platform":
            if (entity.get("ha") or {}).get("platform") not in _as_list(value):
                return False
        elif clause == "missing_group":
            if bool(entity.get("groups")) == bool(value):
                return False
        else:
            raise ValueError(f"where: unknown clause {clause!r}")
    return True


# --------------------------------------------------------------------------- #
# emit: one canonical house style (strips _tags / _-prefixed metadata)
# --------------------------------------------------------------------------- #
def _is_empty(value) -> bool:
    return value is None or (isinstance(value, (list, tuple, dict)) and len(value) == 0)


def yaml_str(value) -> str:
    """Scalar -> YAML text, quoting only when a bare token would misparse."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        text = repr(value)
        # YAML's float syntax needs a dot in the mantissa and a signed exponent;
        # repr(1e-05) == '1e-05' would load back as a *string*.
        if "e" in text:
            mantissa, _, exponent = text.partition("e")
            if "." not in mantissa:
                mantissa += ".0"
            if exponent[0] not in "+-":
                exponent = "+" + exponent
            text = f"{mantissa}e{exponent}"
        return text
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if (
        text == ""
        or any(c in text for c in ":#%°'\"\\{}[],&*!|>@`")
        or text[0] in "-+. "
        or text[-1] == " "
        or text[0].isdigit()
        or text.lower() in ("null", "true", "false", "yes", "no", "on", "off", "~")
    ):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def _emit_key(key) -> str:
    if isinstance(key, bool):
        return yaml_str(key)
    if isinstance(key, int):
        return str(key)
    return yaml_str(str(key))


def _emit_inline_list(values) -> str:
    return "[" + ", ".join(yaml_str(v) for v in values) + "]"


def _emit_value(buf, indent: str, key, value) -> None:
    """Emit ``key: value`` at ``indent`` for a device/ha/template field (block dicts,
    inline scalar lists, literal block scalars for multi-line Jinja)."""
    label = _emit_key(key)
    if isinstance(value, dict):
        clean = {k: v for k, v in value.items() if not str(k).startswith("_") and not _is_empty(v)}
        if not clean:
            buf.write(f"{indent}{label}: {{}}\n")
            return
        buf.write(f"{indent}{label}:\n")
        for k, v in clean.items():
            _emit_value(buf, indent + "  ", k, v)
    elif isinstance(value, list):
        if all(not isinstance(v, (dict, list)) for v in value) and len(_emit_inline_list(value)) <= 70:
            buf.write(f"{indent}{label}: {_emit_inline_list(value)}\n")
        else:
            buf.write(f"{indent}{label}:\n")
            for item in value:
                if isinstance(item, dict):
                    buf.write(f"{indent}  -\n")
                    for k, v in item.items():
                        _emit_value(buf, indent + "    ", k, v)
                else:
                    buf.write(f"{indent}  - {yaml_str(item)}\n")
    elif isinstance(value, str) and "\n" in value:
        buf.write(f"{indent}{label}: |-\n")
        for line in value.rstrip("\n").split("\n"):
            buf.write(f"{indent}  {line}\n" if line else "\n")
    else:
        buf.write(f"{indent}{label}: {yaml_str(value)}\n")


def _emit_field(buf, name: str, value) -> None:
    """One ordered register field at 4-space indent."""
    if name == "mask" and isinstance(value, int) and not isinstance(value, bool):
        buf.write(f"    mask: 0x{value:X}\n")
    elif name == "groups":
        buf.write(f"    groups: {_emit_inline_list(value)}\n")
    elif name == "write_value" and isinstance(value, list):
        buf.write("    write_value:\n")
        for item in value:
            buf.write(f"      - {yaml_str(item)}\n")
    elif isinstance(value, list):
        buf.write(f"    {name}: {_emit_inline_list(value)}\n")
    else:
        buf.write(f"    {name}: {yaml_str(value)}\n")


def _emit_register_entity(buf, entity: dict) -> None:
    buf.write(f"  {entity['key']}:\n")
    for name in ENTITY_FIELD_ORDER:
        if not _is_empty(entity.get(name)):
            _emit_field(buf, name, entity[name])
    # any non-underscore key we do not know about — emit it too so validate() flags it
    for name, value in entity.items():
        if name not in _KNOWN_ENTITY_KEYS and not str(name).startswith("_") and not _is_empty(value):
            _emit_value(buf, "    ", name, value)
    for block in ("map", "flags"):
        if not _is_empty(entity.get(block)):
            buf.write(f"    {block}:\n")
            for k, v in entity[block].items():
                _emit_value(buf, "      ", k, v)
    if "read_register" in entity:
        buf.write(f"    read_register: {yaml_str(entity['read_register'])}\n")
    if entity.get("internal"):
        buf.write("    internal: true\n")
        return
    if entity.get("ha"):
        buf.write("    ha:\n")
        for k, v in _ordered_ha_items(entity["ha"]):
            if not _is_empty(v):
                _emit_value(buf, "      ", k, v)


def _emit_template_entity(buf, entity: dict) -> None:
    buf.write(f"  {entity['key']}:\n")
    if entity.get("ha"):
        buf.write("    ha:\n")
        for k, v in _ordered_ha_items(entity["ha"]):
            if not _is_empty(v):
                _emit_value(buf, "      ", k, v)
    for name, value in entity.items():
        if name in ("key", "ha") or str(name).startswith("_") or _is_empty(value):
            continue
        if name == "groups":
            buf.write(f"    groups: {_emit_inline_list(value)}\n")
        else:
            _emit_value(buf, "    ", name, value)


def _emit_device(buf, device: dict) -> None:
    buf.write(f"# {SECTION_COMMENTS['device']}\n")
    buf.write("device:\n")
    body = dict(device)
    default_groups = body.pop("default_groups", None)
    group_labels = body.pop("group_labels", None)
    split_before = body.pop("split_before", None)
    for key, value in body.items():
        if not str(key).startswith("_") and not _is_empty(value):
            _emit_value(buf, "  ", key, value)
    if split_before:
        inner = ", ".join(
            f"{table}: [{', '.join(str(a) for a in addrs)}]"
            for table, addrs in split_before.items()
        )
        buf.write(f"  split_before: {{ {inner} }}\n")
    if default_groups:
        buf.write(f"  default_groups: {_emit_inline_list(default_groups)}\n")
    if group_labels:
        buf.write("  group_labels:\n")
        for name, label in group_labels.items():
            buf.write(f"    {name}: {yaml_str(label)}\n")


def emit(ir: dict, header: str | None = None) -> str:
    """Serialize the intermediate to canonical YAML (strips ``_``-prefixed metadata)."""
    buf = io.StringIO()
    if header:
        buf.write(f"# {header}\n")
    _emit_device(buf, ir.get("device") or {})
    for table in TABLES:
        # Preserve each converter's natural entity order (upstream/source/curated);
        # a converter that wants address order sorts before handing entities over.
        rows = [e for e in ir.get(table, []) if e]
        if not rows:
            continue
        buf.write(f"\n# {SECTION_COMMENTS[table]}\n{table}:\n")
        for entity in rows:
            _emit_register_entity(buf, entity)
    templates = ir.get("template") or []
    if templates:
        buf.write(f"\n# {SECTION_COMMENTS['template']}\ntemplate:\n")
        for entity in templates:
            _emit_template_entity(buf, entity)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# validate + load + the single public entry point
# --------------------------------------------------------------------------- #
def validate(text: str, filename: str) -> None:
    """Round-trip the emitted YAML through the integration's schema, so an emitter
    or augment bug fails the conversion loudly instead of the config entry later."""
    sys.path.insert(0, str(_DEST_DIR.parents[1]))  # .../custom_components
    from modbus_connect.schema import parse_device  # noqa: PLC0415

    parse_device(yaml.safe_load(text), filename=filename)


def load(path: str | Path) -> dict | None:
    """Parse a ``<device>/augment.yaml``; ``None`` if the file is absent (strip-only)."""
    path = Path(path)
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_augmented(
    ir: dict,
    device_name: str,
    *,
    header: str | None = None,
    augment_dir: str | Path | None = None,
    dest_dir: str | Path | None = None,
) -> dict:
    """THE single call converters make per device. Loads ``support/converter/
    <device_name>/augment.yaml`` (absent → strip-only), applies its ops, emits the
    canonical YAML, validates it, and writes ``device_configs/<device_name>.yaml``.

    Returns a small ``{table: count}`` summary for logging."""
    augment_dir = Path(augment_dir) if augment_dir else _CONVERTER_DIR
    dest_dir = Path(dest_dir) if dest_dir else _DEST_DIR

    spec = load(augment_dir / device_name / "augment.yaml")
    final = apply(ir, spec)
    if header is None:
        header = (
            f"Generated by the converter — do not edit here; "
            f"edit support/converter/{device_name}/augment.yaml and re-run."
        )
    text = emit(final, header)
    validate(text, f"{device_name}.yaml")

    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / f"{device_name}.yaml").write_text(text, encoding="utf-8")
    return {section: len(final.get(section, [])) for section in SECTIONS if final.get(section)}
