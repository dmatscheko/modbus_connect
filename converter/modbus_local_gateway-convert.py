#!/usr/bin/env python3
"""Convert modbus_local_gateway device YAML files to the modbus_connect format.

Standalone: needs only PyYAML, no Home Assistant.

Usage:
    python3 convert.py OLD.yaml [MORE.yaml ...] -o OUTPUT_DIR
    python3 convert.py OLD_DIR -o OUTPUT_DIR
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

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


class HexInt(int):
    """Integer dumped as hex (for masks)."""


def _hexint_representer(dumper: yaml.Dumper, value: HexInt) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:int", f"0x{value:X}")


yaml.SafeDumper.add_representer(HexInt, _hexint_representer)


# One-line explanation written above each top-level section in the output YAML,
# so the generated files are self-documenting (size + read/write access).
SECTION_COMMENTS = {
    "device": "Device metadata: manufacturer and model, plus optional read/poll tuning.",
    "holding": "Holding registers: 16-bit words, read/write (Modbus FC03 read, FC06/FC16 write).",
    "input": "Input registers: 16-bit words, read-only (Modbus FC04 read).",
    "coil": "Coils: single-bit booleans, read/write (Modbus FC01 read, FC05 write).",
    "discrete": "Discrete inputs: single-bit booleans, read-only (Modbus FC02 read).",
    "template": "Templates: composite Home Assistant entities derived from the registers above.",
}


def dump_device_yaml(fh: Any, doc: dict[str, Any]) -> None:
    """Write a device document, prefixing each top-level section with a comment.

    PyYAML's ``safe_dump`` cannot attach comments to nodes, so each section is
    dumped on its own and its :data:`SECTION_COMMENTS` line is written first.
    """
    for index, (section, body) in enumerate(doc.items()):
        if index:
            fh.write("\n")  # blank line between sections
        comment = SECTION_COMMENTS.get(section)
        if comment:
            fh.write(f"# {comment}\n")
        yaml.safe_dump(
            {section: body}, fh, sort_keys=False, allow_unicode=True, width=100
        )


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
            new["mask"] = HexInt(mask)
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
        if "on" in old:
            new["on"] = old["on"]
        if "off" in old:
            new["off"] = old["off"]
    elif platform == "switch":
        switch = old.get("switch") or {}
        if "on" in switch:
            new["on"] = switch["on"]
        if "off" in switch:
            new["off"] = switch["off"]
    elif platform == "select":
        options = old.get("options") or {}
        if not options:
            raise SkipEntity("select without 'options' cannot be converted")
        new["map"] = options
    elif platform == "number":
        number = old.get("number") or {}
        if "min" in number:
            ha["min"] = number["min"]
        if "max" in number:
            ha["max"] = number["max"]
        if "step" in number:
            ha["step"] = number["step"]
        if isinstance(number.get("mode"), str):
            ha["mode"] = number["mode"].lower()

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


def convert_file(path: Path, out_dir: Path) -> int:
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict):
        warn(path.name, "not a YAML mapping, skipped")
        return 0
    if not (set(doc) & set(SECTION_TO_TABLE)):
        warn(path.name, "no old-format sections found (already converted?), skipped")
        return 0
    new_doc = convert_device(doc, path.name)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / path.name
    with out_path.open("w", encoding="utf-8") as fh:
        fh.write(f"# Converted from modbus_local_gateway '{path.name}' by convert.py\n")
        dump_device_yaml(fh, new_doc)
    count = sum(len(new_doc.get(s, {})) for s in SECTION_TO_TABLE.values())
    print(f"  {path.name}: {count} entities -> {out_path}")
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
