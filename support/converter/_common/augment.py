#!/usr/bin/env python3
"""Common augmentation library — the single writer of the bundled device configs.

Every converter (SolaX / modbus_local_gateway / Dimplex-Pichler) builds a *tagged
intermediate* in memory and hands it to :func:`write_augmented`, which is the only
code in the repo that emits a ``device_configs/*.yaml`` file. Because all devices
flow through this one function, every bundled file comes out in the same canonical
style.

Pipeline (nothing is written to disk except the final config):

    intermediate  --load(devicedocs/<slug>/augment.yaml)-->  spec  # declarative policy
    intermediate  --apply(spec)-->                   final       # ordered ops
    final         --emit(header)-->                  text        # canonical YAML, _tags stripped
    text          --validate-->                      parse_device round-trip
    write custom_components/modbus_connect/device_configs/<slug>.yaml  # slug == devicedocs folder

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
in ``support/devicedocs/<slug>/augment.yaml``. See the module ``README``/DSL below.
"""
from __future__ import annotations

import io
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

# support/converter/_common/augment.py  ->  parents: _common, converter, support, <repo>
_COMMON_DIR = Path(__file__).resolve().parent
_SUPPORT_DIR = Path(__file__).resolve().parents[2]
_REPO_DIR = _SUPPORT_DIR.parent
_DEST_DIR = _REPO_DIR / "custom_components/modbus_connect/device_configs"

# The integration's HA-import-free model module is the single source of the
# table vocabulary; import it (under its canonical package name, so tests and
# tools share one module object) instead of mirroring it.
sys.path.insert(0, str(_REPO_DIR))
from custom_components.modbus_connect.models import TABLES  # noqa: E402

# A device's grouping/patch policy and its manufacturer docs live together, in the same
# per-device folder under support/devicedocs/<slug>/ (augment.yaml + registers.md + …).
_DEVICEDOCS_DIR = _SUPPORT_DIR / "devicedocs"
# The shared translate-once memory: every source string's per-language text, applied
# to any device that uses the string (a device's own translations: block overrides it).
_SHARED_TRANSLATIONS = _DEVICEDOCS_DIR / "translations.yaml"
# Canonical map: bundled config basename -> its support/devicedocs/<slug> folder. Single
# source of truth (JSON so importlib-loaded copies of this module need no sibling import).
_DEVICE_FOLDERS = json.loads((_COMMON_DIR / "device_folders.json").read_text(encoding="utf-8"))
_SLUGS = frozenset(_DEVICE_FOLDERS.values())


def folder_for(source_name: str, augment_dir: str | Path | None = None) -> str:
    """The ``support/devicedocs/<slug>`` folder holding ``source_name``'s policy and docs.

    ``source_name`` may be a *source* basename (an upstream file the MLG converter
    imports, e.g. ``SDM630``) or the ``<slug>`` itself (owned devices are identified
    by their devicedocs folder, which is also the output filename). Both resolve to
    the slug; the emitted config is always ``device_configs/<slug>.yaml``."""
    slug = _DEVICE_FOLDERS.get(f"{source_name}.yaml")
    if slug is not None:
        return slug
    if source_name in _SLUGS:
        return source_name
    # A slug naming a devicedocs folder that carries a device.yaml — a brand-new owned
    # device, not (yet) in device_folders.json — resolves to itself. So dropping in a
    # support/devicedocs/<slug>/device.yaml is all it takes to own a device.
    base = Path(augment_dir) if augment_dir else _DEVICEDOCS_DIR
    if (base / source_name / "device.yaml").is_file():
        return source_name
    raise KeyError(
        f"{source_name!r} is not in support/converter/_common/device_folders.json, "
        f"is not a known slug, and support/devicedocs/{source_name}/device.yaml does "
        f"not exist — add its config-basename -> devicedocs-folder mapping, or a device.yaml."
    )


def is_owned(slug: str, augment_dir: str | Path | None = None) -> bool:
    """Whether ``slug`` is an **owned** device — its hand-maintained source of truth
    ``support/devicedocs/<slug>/device.yaml`` exists.

    Ownership is filesystem state, not a hard-coded list: an import tool skips an owned
    device (so a re-import never clobbers hand curation), and ``convert_all`` regenerates
    it from that file via :func:`write_owned`. Drop a ``device.yaml`` into a device's
    folder and it becomes owned; delete it and the device goes back to import-generated.
    """
    base = Path(augment_dir) if augment_dir else _DEVICEDOCS_DIR
    return (base / slug / "device.yaml").is_file()


def owned_slugs(augment_dir: str | Path | None = None) -> tuple[str, ...]:
    """Every owned device slug, sorted — the ``support/devicedocs/*`` folders that carry
    a ``device.yaml``. ``convert_all`` regenerates exactly these through ``write_owned``."""
    base = Path(augment_dir) if augment_dir else _DEVICEDOCS_DIR
    return tuple(sorted(p.parent.name for p in base.glob("*/device.yaml")))


# Editor autocomplete + validation: the yaml-language-server modeline must be the file's
# very first line (see CONTRIBUTING.md). ``emit`` writes it verbatim above the header.
SCHEMA_DIRECTIVE = (
    "# yaml-language-server: $schema=https://raw.githubusercontent.com/"
    "dmatscheko/modbus_connect/main/docs/device_files.schema.json"
)


# The command that regenerates every bundled config (from convert_all.py's docs), shown in
# each file's header so a reader knows exactly how to reproduce it.
_REGEN_CMD = (
    "  MLG_GATEWAY_REPO=/path/to/modbus_local_gateway \\",
    "  SOLAX_MODBUS_REPO=/path/to/homeassistant-solax-modbus \\",
    "    .venv/bin/python support/converter/convert_all.py",
)


def _repo_rel(path: str | Path) -> str:
    """Best-effort repo-relative path string for a converter script (its ``__file__``)."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(_SUPPORT_DIR.parent))
    except ValueError:
        return resolved.name


def _compose_header(
    source: str, variant: str | Path, folder: str, note: str | None, *, owned: bool = False
) -> str:
    """The canonical config header: which converter variant produced it from which source,
    that it must not be hand-edited, where to edit its entries, and how to regenerate.

    ``owned`` devices have no upstream import — their source of truth is the
    hand-maintained ``device.yaml`` in the same folder, so the header points there
    and the regen command needs no external checkouts."""
    if owned:
        lines = [
            f"Generated from {source} —",
            f"do not edit here; edit support/devicedocs/{folder}/device.yaml and re-run:",
            "  .venv/bin/python support/converter/convert_all.py",
        ]
    else:
        lines = [
            f"Generated by the converter (variant {_repo_rel(variant)}) from {source} —",
            f"do not edit here; edit support/devicedocs/{folder}/augment.yaml and re-run:",
            *_REGEN_CMD,
        ]
    if note:
        lines.append(note)
    return "\n".join(lines)

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
    "translations": "Translations: per-language text for this device's human-facing strings "
    "(device model, group labels, entity names, map/flag values), keyed by the source string.",
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


def intermediate_from_device_file(doc: dict) -> dict:
    """A finished device file (the bundled output format) -> a tagged intermediate.

    The inverse of :func:`emit`: each table's ``{key: fields}`` mapping becomes an
    ordered list of entities (the key folded back in), the ``template`` section
    likewise, and the keyed ``translations`` catalog becomes the list-of-units form
    :func:`resolve_translations` re-keys. No ``_tags`` are stamped — an owned device
    carries no augment.yaml ops to match against, so nothing needs converter facts.

    This is how an owned device (one with a hand-maintained ``device.yaml``) enters
    the pipeline instead of an upstream import."""
    ir = intermediate(doc.get("device") or {})
    for table in TABLES:
        for key, fields in (doc.get(table) or {}).items():
            add_entity(ir, table, key, **fields)
    for key, fields in (doc.get("template") or {}).items():
        add_entity(ir, "template", key, **fields)
    translations = doc.get("translations")
    if isinstance(translations, dict):
        # emit writes {source: {lang: text}}; the resolver wants the list-of-units
        # form, matched back to source strings by any of their language values.
        ir["translations"] = list(translations.values())
    return ir


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
    if spec.get("translations"):
        ir["translations"] = [*(ir.get("translations") or []), *spec["translations"]]
    for op in spec.get("ops", []) or []:
        _apply_op(ir, op)
    return ir


def _apply_op(ir: dict, op: dict) -> None:
    # One verb per op: the dispatch below is first-match-wins, so a second verb
    # would be silently ignored (half-applied policy) instead of applied.
    verbs = [v for v in ("add", "remove", "group", "set", "unset", "tag", "untag") if v in op]
    if len(verbs) > 1:
        raise ValueError(f"augment op combines {verbs}; split it into one op per verb: {op!r}")
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
        if any(e.get("key") == new["key"] for e in section):
            raise ValueError(f"add: key {new['key']!r} already exists in {table!r}")
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
    buf.write(f"\n# {SECTION_COMMENTS['device']}\n")
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


def _emit_translations(buf, translations: dict) -> None:
    """The optional top-level ``translations:`` catalog (source string -> {lang: text})."""
    buf.write(f"\n# {SECTION_COMMENTS['translations']}\n")
    buf.write("translations:\n")
    for source, langs in translations.items():
        if not _is_empty(langs):
            _emit_value(buf, "  ", source, langs)


def _check_unique_keys(section: str, rows: list[dict]) -> None:
    """Duplicate keys in one section would be silently collapsed to the last
    entry by every YAML loader — the file would validate while an entity is
    lost. Cross-section duplicates are caught loudly by parse_device; only the
    same-section case is invisible downstream, so the single writer refuses it."""
    keys = [e.get("key") for e in rows]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    if dupes:
        raise ValueError(f"duplicate {section} keys: {dupes}")


def emit(ir: dict, header: str | None = None) -> str:
    """Serialize the intermediate to canonical YAML (strips ``_``-prefixed metadata).

    The first line is always the ``yaml-language-server`` schema directive, so editors
    offer autocomplete + validation on every generated config (see ``SCHEMA_DIRECTIVE``)."""
    buf = io.StringIO()
    buf.write(f"{SCHEMA_DIRECTIVE}\n")
    if header:
        for line in header.split("\n"):
            buf.write(f"# {line}\n" if line else "#\n")
    # Device first (the important part); each section writes its own leading blank line.
    _emit_device(buf, ir.get("device") or {})
    for table in TABLES:
        # Preserve each converter's natural entity order (upstream/source/curated);
        # a converter that wants address order sorts before handing entities over.
        rows = [e for e in ir.get(table, []) if e]
        if not rows:
            continue
        _check_unique_keys(table, rows)
        buf.write(f"\n# {SECTION_COMMENTS[table]}\n{table}:\n")
        for entity in rows:
            _emit_register_entity(buf, entity)
    templates = ir.get("template") or []
    if templates:
        _check_unique_keys("template", templates)
        buf.write(f"\n# {SECTION_COMMENTS['template']}\ntemplate:\n")
        for entity in templates:
            _emit_template_entity(buf, entity)
    # Translations last: ``resolve_translations`` turned the input lists of {lang: text}
    # units into the per-device ``{source: {lang: text}}`` catalog; it is often long, so it
    # sits at the bottom, after the device/register sections.
    if isinstance(ir.get("translations"), dict) and ir["translations"]:
        _emit_translations(buf, ir["translations"])
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# validate + load + the single public entry point
# --------------------------------------------------------------------------- #
def validate(text: str, filename: str) -> None:
    """Round-trip the emitted YAML through the integration's schema, so an emitter
    or augment bug fails the conversion loudly instead of the config entry later.
    Imported lazily (unlike models above): schema pulls in Home Assistant."""
    from custom_components.modbus_connect.schema import parse_device

    parse_device(yaml.safe_load(text), filename=filename)


def load(path: str | Path) -> dict | None:
    """Parse a ``<device>/augment.yaml``; ``None`` if the file is absent (strip-only)."""
    path = Path(path)
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_shared_translations(path: str | Path | None = None) -> list:
    """The shared translate-once memory: a list of ``{lang: text}`` translation
    units, each matched against a source string by *any* of its language values
    (so one unit serves the German source and the English source alike). ``[]`` if absent."""
    path = Path(path) if path else _SHARED_TRANSLATIONS
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


# A pure value label — a number with an optional unit ("-19 °C", "50 %", "3") —
# carries no translatable words, so it is never collected or reported.
_NUMERIC_LABEL = re.compile(
    r"[+-]?[\d.,]+\s*(°C|°F|%|K|Ω|V|A|W|VA|Hz|kWh|Wh|rpm|bar|h|min|s)?", re.IGNORECASE
)


def _worth_translating(text: str) -> bool:
    return not _NUMERIC_LABEL.fullmatch(text.strip())


def _collect_translatable(ir: dict) -> tuple[list[str], list[str]]:
    """Every human-facing string the integration localizes, in first-seen order,
    split into ``(enum_like, names)``. ``enum_like`` — the device model, group
    labels, and ``map:``/``flags:`` values — drives states, group switches, and
    template ``key()`` comparisons, so untranslated ones are worth listing;
    ``names`` (entity/template display names) are display-only. Pure numeric value
    labels are skipped (nothing to translate)."""
    enum_like: dict[str, None] = {}
    names: dict[str, None] = {}

    def add(bucket: dict[str, None], value: object) -> None:
        if isinstance(value, str) and value.strip() and _worth_translating(value):
            bucket.setdefault(value, None)

    device = ir.get("device") or {}
    add(enum_like, device.get("model"))
    for label in (device.get("group_labels") or {}).values():
        add(enum_like, label)
    for _section, entity in _iter(ir):
        add(names, (entity.get("ha") or {}).get("name"))
        for block in ("map", "flags"):
            for value in (entity.get(block) or {}).values():
                add(enum_like, value)
    for shared in enum_like:  # a string used both ways counts as enum_like
        names.pop(shared, None)
    return list(enum_like), list(names)


def _translation_index(units: object, origin: str) -> dict[str, dict[str, str]]:
    """Index a list of ``{lang: text}`` translation units by *every* language value
    they contain, so a source string in any language finds its unit. Warns when one
    value maps to two conflicting units (an ambiguous lookup — disambiguate by making
    the value unique, e.g. rename one, or override it in the device's augment.yaml)."""
    index: dict[str, dict[str, str]] = {}
    for unit in units if isinstance(units, list) else []:
        if not isinstance(unit, dict):
            continue
        texts = {lang: t for lang, t in unit.items() if isinstance(t, str) and t}
        for value in texts.values():
            if value in index and index[value] != texts:
                print(
                    f"  WARNING {origin}translations: {value!r} maps to two different "
                    f"units ({index[value]} vs {texts}) — the lookup is ambiguous; keeping "
                    f"the first. Make the value unique or override it per device.",
                    file=sys.stderr,
                )
                continue
            index[value] = texts
    return index


def resolve_translations(ir: dict, shared_units: object) -> tuple[list[str], list[str]]:
    """Replace ``ir['translations']`` with this device's emitted catalog and report gaps.

    Both the shared memory and the device's own ``translations:`` are lists of
    ``{lang: text}`` units, matched against a source string by any of their language
    values. For every translatable string the file uses, the shared unit is looked up
    and the device unit (if any) overrides it per language. The emitted catalog is
    keyed by the actual source string, so the integration's lookup is unchanged and the
    file carries exactly what it needs. Returns ``(untranslated_enum, untranslated_names)``.
    """
    shared_index = _translation_index(shared_units, "shared ")
    device_index = _translation_index(ir.get("translations"), "")
    enum_like, names = _collect_translatable(ir)
    resolved: dict[str, dict] = {}
    for source in [*enum_like, *names]:
        merged = {**shared_index.get(source, {}), **device_index.get(source, {})}
        if merged:
            resolved[source] = merged
    ir["translations"] = resolved
    return (
        [s for s in enum_like if s not in resolved],
        [s for s in names if s not in resolved],
    )


_JINJA_LITERAL = re.compile(r"""['"]([^'"]+)['"]""")


def _walk_strings(node: object):
    """Yield every string reachable inside a (possibly nested) template entity."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _walk_strings(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _walk_strings(value)


def label_comparisons_in_templates(ir: dict, resolved: dict) -> dict[str, set[str]]:
    """Find template Jinja that still references a *translated* label as a quoted
    literal (``== 'Sommer'``, ``{'Zuluft': …}``, ``not in ['Stufe 1']``). These
    break the moment the language changes, because the decoded value moves but the
    literal does not — they must compare the stable map key via ``key('entity')``.
    Returns ``{template key: {offending labels}}``."""
    hits: dict[str, set[str]] = {}
    for entity in ir.get("template", []):
        for text in _walk_strings(entity):
            if "{{" not in text and "{%" not in text:
                continue  # only Jinja bodies; plain action-map labels are fine
            for literal in _JINJA_LITERAL.findall(text):
                if literal in resolved:
                    hits.setdefault(entity.get("key", "?"), set()).add(literal)
    return hits


def _warn_label_comparisons(source_name: str, ir: dict) -> None:
    for key, labels in label_comparisons_in_templates(ir, ir.get("translations") or {}).items():
        for label in sorted(labels):
            print(
                f"  WARNING {source_name}: template '{key}' compares the translated label "
                f"{label!r} as a literal — use key('<entity>') == <map key> instead, "
                f"or it will break in other languages",
                file=sys.stderr,
            )


def _report_translation_coverage(
    source_name: str, resolved: dict, untranslated_enum: list[str], untranslated_names: list[str]
) -> None:
    """One-line coverage summary per translated device, plus the untranslated
    enum/label strings (the ones that matter for states and templates). A device
    with no translations at all stays silent — it is simply single-language."""
    if not resolved:
        return
    print(
        f"  {source_name}: translations — {len(resolved)} applied; untranslated: "
        f"{len(untranslated_enum)} enum/label, {len(untranslated_names)} name(s)",
        file=sys.stderr,
    )
    cap = 40
    for source in untranslated_enum[:cap]:
        print(f"    untranslated enum/label: {source!r}", file=sys.stderr)
    if len(untranslated_enum) > cap:
        print(f"    ... and {len(untranslated_enum) - cap} more enum/label strings", file=sys.stderr)


def strip_disabled_by_default(ir: dict) -> None:
    """Drop every ``ha.enabled_by_default: false`` from an intermediate (in place).

    A ready-made ``transform=`` for ``write_augmented``: for device families whose
    visibility is fully controlled by the group/tier system, the upstream per-entity
    "disabled by default" flag is redundant and even conflicts with it (a ``basic``
    entity marked disabled). This filters the OUTPUT only — the source flags stay put,
    so a converter can restore them by not passing this transform."""
    for section in SECTIONS:
        for entity in ir.get(section, []) or []:
            ha = entity.get("ha")
            if isinstance(ha, dict) and ha.get("enabled_by_default") is False:
                ha.pop("enabled_by_default")


def write_augmented(
    ir: dict,
    source_name: str,
    *,
    source: str | None = None,
    variant: str | Path | None = None,
    note: str | None = None,
    header: str | None = None,
    owned: bool = False,
    transform: Callable[[dict], None] | None = None,
    augment_dir: str | Path | None = None,
    dest_dir: str | Path | None = None,
) -> dict | None:
    """THE single call converters make per device. Loads the device's policy from
    ``support/devicedocs/<slug>/augment.yaml`` (absent → strip-only), applies its ops,
    emits the canonical YAML, validates it, and writes ``device_configs/<slug>.yaml``
    (the slug from ``folder_for(source_name)`` — never the raw ``source_name``).

    The file header is composed here (one canonical format): pass ``source`` (what upstream
    this device came from) and ``variant`` (the converter script's ``__file__``); an optional
    ``note`` becomes a trailing header line. ``header`` overrides the composed text entirely.
    ``transform`` is a final in-place tweak of the fully-applied intermediate (after ops,
    before emit) for device-family-wide adjustments a converter wants to make reversibly.

    Returns a ``{table: count}`` summary — or ``None`` when the device is owned in-tree
    (``support/devicedocs/<slug>/device.yaml`` exists) and this is an *import* (``owned``
    is false): the import is skipped so it can never clobber the hand-maintained source.
    ``write_owned`` passes ``owned=True`` to regenerate that same file, so it is not skipped."""
    augment_dir = Path(augment_dir) if augment_dir else _DEVICEDOCS_DIR
    dest_dir = Path(dest_dir) if dest_dir else _DEST_DIR
    folder = folder_for(source_name, augment_dir)
    if not owned and is_owned(folder, augment_dir):
        print(
            f"  {source_name}: owned in-tree "
            f"(support/devicedocs/{folder}/device.yaml) — import skipped"
        )
        return None

    spec = load(augment_dir / folder / "augment.yaml")
    final = apply(ir, spec)
    if transform is not None:
        transform(final)
    # Fold the shared translate-once memory (overridden by the device's own
    # translations:) into the per-device catalog, and report untranslated strings.
    untranslated = resolve_translations(final, load_shared_translations())
    _report_translation_coverage(source_name, final.get("translations") or {}, *untranslated)
    _warn_label_comparisons(source_name, final)
    if header is None:
        header = _compose_header(
            source or "(source unspecified)", variant or __file__, folder, note, owned=owned
        )
    text = emit(final, header)
    # The output filename is the slug (== devicedocs folder), so every bundled
    # config shares one naming scheme with its docs, regardless of the source
    # basename the converter passed in.
    validate(text, f"{folder}.yaml")

    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / f"{folder}.yaml").write_text(text, encoding="utf-8")
    return {section: len(final.get(section, [])) for section in SECTIONS if final.get(section)}


def write_owned(
    slug: str,
    *,
    variant: str | Path | None = None,
    augment_dir: str | Path | None = None,
    dest_dir: str | Path | None = None,
) -> dict:
    """Regenerate an owned device's bundled config from its hand-maintained
    ``support/devicedocs/<slug>/device.yaml`` — no upstream import.

    The device.yaml is the source of truth (same format as the emitted config); it
    is turned into an intermediate and run through the exact same augment pipeline
    as every other device. Shared translations still merge in, and an ``augment.yaml``
    alongside it still applies if present (normally there is none — the policy is
    already baked into device.yaml)."""
    base = Path(augment_dir) if augment_dir else _DEVICEDOCS_DIR
    doc = load(base / slug / "device.yaml")
    if doc is None:
        raise FileNotFoundError(
            f"owned device {slug!r} has no support/devicedocs/{slug}/device.yaml"
        )
    ir = intermediate_from_device_file(doc)
    return write_augmented(
        ir,
        slug,
        source=f"support/devicedocs/{slug}/device.yaml (hand-maintained)",
        variant=variant,
        owned=True,
        augment_dir=augment_dir,
        dest_dir=dest_dir,
    )
