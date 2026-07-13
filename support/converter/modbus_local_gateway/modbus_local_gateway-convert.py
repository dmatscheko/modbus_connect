#!/usr/bin/env python3
"""Convert modbus_local_gateway device YAML files to the modbus_connect format.

Standalone: needs only PyYAML, no Home Assistant.

Usage:
    python3 convert.py OLD.yaml [MORE.yaml ...] -o OUTPUT_DIR
    python3 convert.py OLD_DIR -o OUTPUT_DIR

Most MLG-derived bundled files are byte-identical to this converter's output
and safe to regenerate. These have been HAND-EDITED after conversion and must
NOT be overwritten blindly (diff against fresh output and re-apply):
    test.yaml (annotated example), salda-ris-mcb.yaml (fan+climate templates),
    froeling-bwp300-pv.yaml (repaired 0-indexed flags).

Dimplex and Pichler are NOT produced here — they are owned in-tree (their source of
truth is support/devicedocs/<slug>/device.yaml). Nothing device-specific is needed for
that: write_augmented skips any device whose device.yaml exists, so an owned device is
never overwritten by an import, whichever converter runs.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

import yaml

_COMMON = Path(__file__).resolve().parents[1] / "_common"
_aug_spec = importlib.util.spec_from_file_location("augment", _COMMON / "augment.py")
augment = importlib.util.module_from_spec(_aug_spec)
_aug_spec.loader.exec_module(augment)

SECTION_TO_TABLE = {
    "read_write_word": "holding",
    "read_only_word": "input",
    "read_write_boolean": "coil",
    "read_only_boolean": "discrete",
}
SECTION_DEFAULT_PLATFORM = {
    "read_write_word": "sensor",
    "read_only_word": "sensor",
    "read_write_boolean": "binary_sensor",
    "read_only_boolean": "binary_sensor",
}
# Control types the old integration accepts per section (anything else is
# warned about and never created there — mirrored here so an invalid control
# is skipped instead of converted into an entity that never existed).
SECTION_ALLOWED_CONTROLS = {
    "read_write_word": {"sensor", "number", "select", "text", "switch", "binary_sensor"},
    "read_only_word": {"sensor", "binary_sensor"},
    "read_write_boolean": {"binary_sensor", "switch"},
    "read_only_boolean": {"binary_sensor"},
}

# Old unit presets -> (real unit, device_class, state_class)
UOM_PRESETS: dict[str, tuple[str, str | None, str | None]] = {
    "Celsius": ("°C", "temperature", "measurement"),
    "Volts": ("V", "voltage", "measurement"),
    "Amps": ("A", "current", "measurement"),
    "kWh": ("kWh", "energy", "total_increasing"),
    "Hz": ("Hz", "frequency", "measurement"),
    "Watts": ("W", "power", "measurement"),
    "Degrees": ("°", None, "measurement"),
    "kVArh": ("kVArh", None, "total_increasing"),
    "VAr": ("var", "reactive_power", "measurement"),
    "VoltAmps": ("VA", "apparent_power", "measurement"),
    "Seconds": ("s", "duration", "total_increasing"),
    "%": ("%", None, "measurement"),
}

# Invalid device_class values found in old configs, silently ignored by HA
DEVICE_CLASS_FIXUPS = {"co2": "carbon_dioxide"}

KNOWN_OLD_KEYS = {
    "name", "address", "size", "float", "signed", "string", "swap", "sum_scale",
    "shift_bits", "bits", "multiplier", "offset", "map", "flags", "precision",
    "unit_of_measurement", "device_class", "state_class", "icon", "entity_category",
    "entity_registry_enabled_default", "never_resets", "max_change", "scan_interval",
    "control", "number", "switch", "options", "on", "off",
}


def warn(filename: str, message: str) -> None:
    print(f"  WARNING {filename}: {message}", file=sys.stderr)


class SkipEntity(Exception):
    """This entity cannot be represented in the new format; skip it with a warning."""


def _convert_type(old: dict, filename: str, key: str) -> dict[str, Any]:
    """Old float/signed/string/size flags -> new type/count."""
    out: dict[str, Any] = {}
    size = old.get("size", 1)
    if old.get("string"):
        out["type"] = "string"
        out["count"] = size
    elif old.get("sum_scale") is not None:
        pass  # implied uint16, count = len(sum_scale)
    elif old.get("float"):
        out["type"] = {2: "float32", 4: "float64"}.get(size)
        if out["type"] is None:
            warn(filename, f"{key}: float with size {size} is invalid; keeping float32")
            out["type"] = "float32"
    else:
        signed = bool(old.get("signed"))
        out["type"] = {
            (1, False): "uint16", (1, True): "int16",
            (2, False): "uint32", (2, True): "int32",
            (4, False): "uint64", (4, True): "int64",
        }.get((size, signed))
        if out["type"] is None:
            warn(filename, f"{key}: size {size} is invalid for integers; keeping uint16")
            out["type"] = "uint16"
        if out["type"] == "uint16":
            del out["type"]  # the default
    return out


def _convert_mask(old: dict, size: int) -> int | None:
    """Old bits + shift_bits -> a single mask."""
    bits = old.get("bits")
    shift = old.get("shift_bits") or 0
    if bits is None and not shift:
        return None
    width = 16 * size
    if bits is None:
        return (((1 << width) - 1) >> shift) << shift
    return ((1 << bits) - 1) << shift


def _convert_uom(old: dict, platform: str, filename: str, key: str) -> dict[str, Any]:
    """Replicate old get_uom(): presets, defaults, and state_class rules."""
    ha: dict[str, Any] = {}
    unit = old.get("unit_of_measurement")
    preset = UOM_PRESETS.get(unit) if isinstance(unit, str) else None
    device_class = old.get("device_class") or (preset[1] if preset else None)
    if device_class in DEVICE_CLASS_FIXUPS:
        warn(filename, f"{key}: device_class '{device_class}' is not a valid HA class "
                       f"(was silently ignored before); using "
                       f"'{DEVICE_CLASS_FIXUPS[device_class]}'")
        device_class = DEVICE_CLASS_FIXUPS[device_class]
    state_class = old.get("state_class") or (preset[2] if preset else None) or "measurement"
    if preset:
        unit = preset[0]
    if platform != "sensor" or old.get("string") or device_class is None:
        state_class = None
    if unit is not None:
        # Only sensor and number entities carry a unit in HA; the old format
        # allowed it anywhere, but emitting it elsewhere makes an invalid file.
        if platform in ("sensor", "number"):
            ha["unit_of_measurement"] = unit
        else:
            warn(filename, f"{key}: {platform} entities have no unit in HA, dropped")
    if device_class is not None:
        ha["device_class"] = device_class
    if state_class is not None:
        ha["state_class"] = state_class
    return ha


def convert_entity(key: str, old: dict, section: str, filename: str) -> dict[str, Any]:
    unknown = set(old) - KNOWN_OLD_KEYS
    if unknown:
        warn(filename, f"{key}: dropping unknown keys {sorted(unknown)}")

    platform = old.get("control", SECTION_DEFAULT_PLATFORM[section])
    if platform not in SECTION_ALLOWED_CONTROLS[section]:
        raise SkipEntity(
            f"control '{platform}' is not valid for {section} "
            f"(the old integration skipped it too)"
        )
    if platform == "text" and not old.get("string"):
        # the old integration created these, but its write path raised on every
        # set attempt (a number rendered as text); nothing faithful to emit
        raise SkipEntity("text without 'string: true' was never writable")
    is_bits = SECTION_TO_TABLE[section] in ("coil", "discrete")

    new: dict[str, Any] = {"address": old["address"]}

    if not is_bits:
        new.update(_convert_type(old, filename, key))
        if old.get("sum_scale") is not None:
            new["sum_scale"] = old["sum_scale"]
        if old.get("swap"):
            new["swap"] = old["swap"]
        mask = _convert_mask(old, old.get("size", 1))
        if mask is not None:
            new["mask"] = mask  # emitted as hex by the augment library
        if old.get("multiplier") is not None:
            new["multiplier"] = old["multiplier"]
        if old.get("offset") is not None:
            new["offset"] = old["offset"]
        if old.get("map") is not None:
            new["map"] = old["map"]
        if old.get("flags") is not None:
            # old flags were 1-indexed bit numbers; new are standard 0-indexed
            width = 16 * old.get("size", 1)
            flags = {}
            for k, v in old["flags"].items():
                if not isinstance(k, int) or isinstance(k, bool):
                    warn(filename, f"{key}: flag bit {k!r} is not an integer, dropped")
                elif 1 <= k <= width:
                    flags[k - 1] = v
                else:
                    warn(filename, f"{key}: flag bit {k} exceeds the {width}-bit value "
                                   f"(could never trigger in the old format), dropped")
            if flags:
                new["flags"] = flags

    # platform specifics ------------------------------------------------------
    ha: dict[str, Any] = {"platform": platform}
    if platform == "binary_sensor":
        # Old semantics: is_on = (value == on), everything else is off; 'off' is
        # never looked at for binary sensors. Word registers default to on == 1
        # (True compares equal to 1) — made explicit so any other value reads as
        # off, exactly as before, instead of "any non-zero is on".
        if "on" in old:
            new["on_value"] = old["on"]
        elif not is_bits:
            new["on_value"] = 1
        if "off" in old:
            warn(filename, f"{key}: 'off' is ignored for binary sensors in the old "
                           f"format (anything != on reads as off), dropped")
    elif platform == "switch":
        switch = old.get("switch") or {}
        # Same reading rule as binary sensors: is_on = (value == on), default 1
        # on word registers. off_value is the turn-off write payload (default 0).
        if "on" in switch:
            new["on_value"] = switch["on"]
        elif not is_bits:
            new["on_value"] = 1
        if "off" in switch:
            new["off_value"] = switch["off"]
    elif platform == "select":
        options = old.get("options") or {}
        if not options:
            raise SkipEntity("select without 'options' cannot be converted")
        new["map"] = options
    elif platform == "number":
        number = old.get("number") or {}
        if "min" not in number or "max" not in number:
            # the old integration refuses to create numbers without both
            raise SkipEntity("number without 'min' and 'max' was never created")
        ha["min"] = number["min"]
        ha["max"] = number["max"]
        if "step" in number:
            ha["step"] = number["step"]
        else:
            # the old integration defaults the step to the multiplier, so a 0.1
            # scale accepts 0.1 increments (and a 10 scale only multiples of 10,
            # which is also all the register can represent)
            mult = old.get("multiplier")
            if isinstance(mult, (int, float)) and mult > 0 and mult != 1:
                ha["step"] = mult
        if isinstance(number.get("mode"), str):
            ha["mode"] = number["mode"].lower()

    # The old pipeline applies multiplier/offset BEFORE looking a value up in
    # map/flags (and selects write the mapped key back through the same scaling);
    # ours maps the raw register value. Fold the scaling into the keys when that
    # lands on whole register values — otherwise the entity has no faithful
    # representation.
    if not is_bits and ("map" in new or "flags" in new):
        mult = new.get("multiplier") or 1
        off = new.get("offset") or 0
        if mult != 1 or off != 0:
            if "flags" in new:
                raise SkipEntity(
                    "flags with multiplier/offset test scaled bit positions; "
                    "not representable"
                )
            folded: dict[int, Any] = {}
            for k, v in new["map"].items():
                raw = (k - off) / mult
                if abs(raw - round(raw)) > 1e-9:
                    raise SkipEntity(
                        f"map key {k} is not a whole register value once the "
                        f"multiplier/offset is removed"
                    )
                folded[round(raw)] = v
            new["map"] = folded
            new.pop("multiplier", None)
            new.pop("offset", None)
            warn(filename, f"{key}: multiplier/offset folded into the map keys "
                           f"(the old format scales before mapping)")

    if old.get("max_change") is not None:
        new["max_change"] = old["max_change"]
    if old.get("never_resets"):
        new["never_resets"] = True
    if old.get("scan_interval") is not None:
        new["scan_interval"] = old["scan_interval"]

    # ha block ------------------------------------------------------------------
    if old.get("name"):
        ha["name"] = old["name"]
    ha.update(_convert_uom(old, platform, filename, key))
    if old.get("precision") is not None:
        if platform == "sensor":
            ha["precision"] = old["precision"]
        elif platform == "number":
            warn(filename, f"{key}: numbers have no display precision in HA "
                           f"(use ha.step for input granularity), dropped")
        else:
            warn(filename, f"{key}: {platform} entities have no display precision "
                           f"in HA, dropped")
    if old.get("icon"):
        ha["icon"] = old["icon"]
    if old.get("entity_category"):
        ha["entity_category"] = old["entity_category"]
    if old.get("entity_registry_enabled_default") is not None:
        ha["enabled_by_default"] = old["entity_registry_enabled_default"]

    new["ha"] = ha
    return new


def convert_device(doc: dict, filename: str) -> dict[str, Any]:
    device_old = doc.get("device") or {}
    device: dict[str, Any] = {
        "manufacturer": device_old.get("manufacturer", "Unknown"),
        "model": device_old.get("model", "Unknown"),
    }
    if device_old.get("max_register_read") is not None:
        device["max_register_read"] = device_old["max_register_read"]

    seen: set[str] = set()
    sections: dict[str, dict[str, Any]] = {}
    for old_section, new_section in SECTION_TO_TABLE.items():
        block = doc.get(old_section)
        if not isinstance(block, dict):
            continue
        for key, old in block.items():
            if not isinstance(old, dict):
                warn(filename, f"{key}: not a mapping, skipped")
                continue
            if key in seen:
                renamed = f"{key}_{new_section}"
                while renamed in seen:
                    renamed += "_"
                warn(filename, f"{key}: duplicate entity key across sections, "
                               f"renamed to {renamed}")
                key = renamed
            seen.add(key)
            try:
                sections.setdefault(new_section, {})[key] = convert_entity(
                    key, old, old_section, filename
                )
            except KeyError as err:
                warn(filename, f"{key}: missing required key {err}, skipped")
            except SkipEntity as err:
                warn(filename, f"{key}: {err}, skipped")

    return {"device": device, **sections}


_TABLE_RW = {"holding": "rw", "coil": "rw", "input": "ro", "discrete": "ro"}


def to_intermediate(doc: dict) -> dict:
    """A converted (new-format) doc -> a tagged intermediate for the augment library.

    Stamps the facts a grouping rule matches on: source, table, read/write-ness,
    platform, and the raw name."""
    ir = augment.intermediate(doc.get("device") or {})
    for table in augment.TABLES:
        for key, fields in (doc.get(table) or {}).items():
            name = (fields.get("ha") or {}).get("name") or key
            tags = {"source:mlg", f"table:{table}", f"rw:{_TABLE_RW[table]}", f"raw-name:{name}"}
            platform = (fields.get("ha") or {}).get("platform")
            if platform:
                tags.add(f"platform:{platform}")
            augment.add_entity(ir, table, key, tags=tags, **fields)
    return ir


def convert_file(path: Path, out_dir: Path) -> int:
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict):
        warn(path.name, "not a YAML mapping, skipped")
        return 0
    if not (set(doc) & set(SECTION_TO_TABLE)):
        warn(path.name, "no old-format sections found (already converted?), skipped")
        return 0
    name = path.stem
    ir = to_intermediate(convert_device(doc, path.name))
    if augment.write_augmented(
        ir, name, source=f"modbus_local_gateway '{path.name}'", variant=__file__, dest_dir=out_dir
    ) is None:
        return 0  # owned in-tree — write_augmented reported the skip
    count = sum(len(ir.get(s, ())) for s in augment.TABLES)
    # output is named after the devicedocs slug, not the upstream basename
    print(f"  {path.name}: {count} entities -> {out_dir / f'{augment.folder_for(name)}.yaml'}")
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="old YAML files or directories")
    parser.add_argument("-o", "--out", type=Path, default=Path("converted"),
                        help="output directory (default: ./converted)")
    args = parser.parse_args(argv)

    files: list[Path] = []
    for inp in args.inputs:
        if inp.is_dir():
            files.extend(sorted([*inp.glob("*.yaml"), *inp.glob("*.yml")]))
        elif inp.is_file():
            files.append(inp)
        else:
            print(f"not found: {inp}", file=sys.stderr)
            return 1

    total = 0
    for path in files:
        total += convert_file(path, args.out)
    print(f"Converted {len(files)} file(s), {total} entities.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
