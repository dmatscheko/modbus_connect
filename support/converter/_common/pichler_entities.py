#!/usr/bin/env python3
"""Turn a Pichler LS-Control xlsx row into a Modbus Connect entity dict.

The two Pichler files use their scale columns inconsistently, so the rules here
were verified to reproduce the hand-tuned entries already in the configs (run
this file directly to re-check — it should report 0 scaling mismatches):

  * Setpoints 'Decimal':  LG350 = number of decimal places (mult = 10**-n),
                          LG150 = a literal multiplier (1 / 10 / 0.1).
  * Datapoints 'Number of Decimal': decimal places in both files.
  * Offset (raw) is scaled by the multiplier, matching the config offsets.

Standalone doc-parsing utility for re-deriving Pichler registers from the manufacturer
spreadsheet; not part of the regeneration pipeline (the extras it once produced are now
curated content in the bundled configs). Run directly for the scaling self-test.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sources


def slug(name: str, addr) -> str:
    s = re.sub(r"^\d+\.\s*", "", name)          # strip "003. "
    s = re.split(r"\(", s)[0]                    # drop parenthetical
    s = re.sub(r"[^0-9A-Za-zÄÖÜäöüß]+", "_", s).strip("_").lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return s or f"reg_{addr}"


def clean_name(desc: str, name: str) -> str:
    s = re.sub(r"^\d+\.\s*", "", desc or name).strip()
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()   # drop a trailing (…)
    return s or name


def parse_enum(*texts) -> dict | None:
    for t in texts:
        m = re.search(r"\(([^)]*\d+\s*=[^)]*)\)", t or "")
        if not m:
            continue
        pairs = re.findall(r"(-?\d+)\s*=\s*([^,;]+?)(?=\s*,\s*-?\d+\s*=|\s*$)", m.group(1))
        if len(pairs) >= 2:
            return {int(k): v.strip() for k, v in pairs}
    return None


_UNIT = [(r"\bppm\b", "ppm", "carbon_dioxide"), (r"%", "%", None), (r"°C|deg\b", "°C", "temperature"),
         (r"\bV\b", "V", "voltage"), (r"\bPa\b", "Pa", None),
         (r"\bh\b|Stunde|hour", "h", "duration"), (r"\bmin\b|Minute", "min", "duration"),
         (r"rpm|U/min", "rpm", None)]


def detect_unit(*texts):
    blob = " ".join(t or "" for t in texts)
    for rx, u, dc in _UNIT:
        if re.search(rx, blob):
            return u, dc
    return None, None


def setpoint_mult(tag: str, dec):
    if dec in ("", None):
        return None
    d = float(dec)
    m = d if tag == "LG150" else 10 ** (-int(d))   # LG150 'Decimal' = multiplier; LG350 = places
    return None if m == 1 else m


def datapoint_mult(dec):
    if dec in ("", None):
        return None
    m = 10 ** (-int(float(dec)))
    return None if m == 1 else m


def gen_setpoint(tag: str, rec: dict) -> dict:
    addr = rec["_addr"]
    name = rec.get("Name", "")
    desc = rec.get("Description", "") or name
    mult = setpoint_mult(tag, rec.get("Decimal"))
    off = None
    try:
        o = float(rec.get("Offset", "0"))
        if o:
            off = o * (mult or 1)
    except ValueError:
        pass
    enum = parse_enum(desc, rec.get("Beschreibung", ""), name)
    e = {"address": addr, "_key": slug(name, addr), "_name": clean_name(desc, name)}
    if enum:
        e["platform"] = "select"
        e["map"] = enum
    else:
        e["platform"] = "number"
        try:
            mn, mx = float(rec.get("Min", "")), float(rec.get("Max", ""))
        except ValueError:
            mn = mx = None
        if mn is not None:
            e["min"] = round(mn * (mult or 1) + (off or 0), 4)
            e["max"] = round(mx * (mult or 1) + (off or 0), 4)
        if mult:
            e["multiplier"] = mult
        if off:
            e["offset"] = off
        u, dc = detect_unit(desc, name)
        if u:
            e["unit"] = u
        if dc:
            e["device_class"] = dc
    return e


def gen_datapoint(rec: dict) -> dict:
    addr = rec["_addr"]
    name = rec.get("Name", "")
    desc = rec.get("Description", "") or name
    mult = datapoint_mult(rec.get("Number of Decimal"))
    e = {"address": addr, "_key": slug(name, addr), "_name": clean_name(desc, name), "platform": "sensor"}
    if mult:
        e["multiplier"] = mult
    u, dc = detect_unit(desc, name)
    if u:
        e["unit"] = u
    if dc:
        e["device_class"] = dc
    return e


if __name__ == "__main__":
    # overlap validation: the rules must reproduce the existing config entries.
    import yaml
    for tag, folder, cf in [("LG350", "pichler-lg350-lg450", "Pichler-LG350-LG450.yaml"),
                            ("LG150", "pichler-lg150-lg250", "Pichler-LG150-LG250.yaml")]:
        cfg = yaml.safe_load((sources.CFG / cf).read_text())
        sp = {r["_addr"]: r for r in sources.pichler_records(folder, "Setpoints")}
        mism = 0
        for key, p in (cfg.get("holding") or {}).items():
            a = p.get("address")
            if a not in sp:
                continue
            g = gen_setpoint(tag, sp[a])
            if (p.get("multiplier") or 1) != (g.get("multiplier") or 1) or \
               (p.get("offset") or 0) != (g.get("offset") or 0):
                mism += 1
                print(f"  {tag} MISMATCH addr {a} {key}: cfg mult={p.get('multiplier')} off={p.get('offset')} "
                      f"vs gen mult={g.get('multiplier')} off={g.get('offset')}")
        print(f"{tag}: overlapping holding entries checked, scaling mismatches = {mism}")
