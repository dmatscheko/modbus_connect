#!/usr/bin/env python3
"""Manufacturer-document expansion for the Dimplex and Pichler device families.

The base register set for these three devices comes from their ``modbus_local_gateway``
upstream config (converted mechanically). This module reads the manufacturer's own
Modbus documents — the Pichler LS-Control ``.xlsx`` and the Dimplex NWPM datapoint
``.html`` under ``support/devicedocs/`` — and generates config entities for every
documented register the base does *not* already cover.

It produces plain *facts* only: address, type, scaling, enum, unit-derived
``device_class``/``state_class``, and a raw source name. All *policy* (grouping,
which readings are expert-tier internals, the composite templates, per-entity
overrides) lives in ``support/devicedocs/<slug>/augment.yaml``. Each generated
entity therefore carries a ``_tags`` set the augment rules match on:

    raw-name:<source name>   source:doc   unit:<uom>   internal (raw internal reading)

The scaling rules are verified against the overlapping base entries by
``pichler_entities.py`` (run it directly — it must report 0 scaling mismatches).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import pichler_entities as PG  # noqa: E402  (row -> entity generators + slug/clean_name)
import sources  # noqa: E402  (xlsx / html parsers)

_PICHLER_DOCS = {
    "Pichler-LG150-LG250": ("LG150", "pichler-lg150-lg250"),
    "Pichler-LG350-LG450": ("LG350", "pichler-lg350-lg450"),
}


# --------------------------------------------------------------------------- #
# unit -> HA device_class / state_class (the Dimplex/Pichler unit vocabulary)
# --------------------------------------------------------------------------- #
def unit_dc(*texts: str, name: str = "") -> tuple[str | None, str | None, str | None]:
    """Return ``(unit, device_class, state_class)`` for a blob of source text."""
    blob = " ".join(t or "" for t in texts)
    # A lone "K" unit cell is a temperature *difference* (hysteresis): keep the
    # kelvin unit but no temperature device_class — HA would otherwise convert
    # the delta like an absolute temperature. Checked against the unit cell
    # only; a bare K inside running text is too ambiguous.
    if (texts[0] or "").strip() == "K":
        return "K", None, "measurement"
    if re.search(r"°C|\bdeg", blob):
        return "°C", "temperature", "measurement"
    if re.search(r"\bppm\b", blob):
        return "ppm", ("carbon_dioxide" if re.search(r"co2", blob + name, re.I) else None), "measurement"
    if re.search(r"%\s*rF|rel.*Feuchte|humidity", blob, re.I):
        return "%", "humidity", "measurement"
    if "%" in blob:
        return "%", None, "measurement"
    if re.search(r"\bV\b", blob):
        return "V", "voltage", "measurement"
    if re.search(r"\bPa\b", blob):
        return "Pa", "pressure", "measurement"
    if re.search(r"rpm|U/min", blob):
        return "rpm", None, "measurement"
    return None, None, None


def is_internal_pichler_dp(name: str | None) -> bool:
    """A raw internal reading (ADC counts, supply rails) — expert tier, ungrouped."""
    n = (name or "").strip().upper()
    return n.startswith("PIC_") or n.startswith("ADC") or bool(re.search(r"\b(24V|3V3|3\.3V|RAIL)\b", n))


# --------------------------------------------------------------------------- #
# emit-style dict (from pichler_entities / below) -> config entity fields
# --------------------------------------------------------------------------- #
def _to_fields(e: dict) -> dict:
    """Turn a generator dict (``_key``/``_name``/``platform``/…) into config fields."""
    fields: dict = {"address": e["address"]}
    if e.get("type") and e["type"] != "uint16":
        fields["type"] = e["type"]
    if e.get("multiplier") is not None:
        fields["multiplier"] = e["multiplier"]
    if e.get("offset") is not None:
        fields["offset"] = e["offset"]
    if e.get("map"):
        fields["map"] = e["map"]
    ha: dict = {"platform": e["platform"], "name": e["_name"]}
    if e.get("icon"):
        ha["icon"] = e["icon"]
    if e["platform"] == "number":
        ha["min"] = e.get("min")
        ha["max"] = e.get("max")
        if e.get("step") is not None:
            ha["step"] = e["step"]
    if e.get("unit"):
        ha["unit_of_measurement"] = e["unit"]
    if e.get("device_class"):
        ha["device_class"] = e["device_class"]
    if e.get("state_class") and e["platform"] == "sensor":
        ha["state_class"] = e["state_class"]
    if e.get("entity_category"):
        ha["entity_category"] = e["entity_category"]
    fields["ha"] = ha
    return fields


def _entity(table: str, e: dict, *, source: str, internal: bool = False) -> dict:
    fields = _to_fields(e)
    tags = {f"raw-name:{e['_name']}", f"source:{source}"}
    if e.get("unit"):
        tags.add(f"unit:{e['unit']}")
    if internal:
        tags.add("internal")
    return {"table": table, "key": e["_key"], "tags": tags, "fields": fields}


# --------------------------------------------------------------------------- #
# Pichler (LS-Control xlsx): Setpoints -> holding, Datapoints -> input
# --------------------------------------------------------------------------- #
def pichler_expansion(device_name: str, base_addr: dict[str, set]) -> list[dict]:
    tag, folder = _PICHLER_DOCS[device_name]
    setpoints = sources.pichler_records(folder, "Setpoints")
    datapoints = sources.pichler_records(folder, "Datapoints")
    used: set[str] = set()

    def uniq(key: str) -> str:
        base, i = key, 2
        while key in used:
            key = f"{base}_{i}"
            i += 1
        used.add(key)
        return key

    out: list[dict] = []
    for r in setpoints:
        if r["_addr"] in base_addr["holding"]:
            continue
        e = PG.gen_setpoint(tag, r)
        desc = (r.get("Description", "") + " " + r.get("Beschreibung", "")).lower()
        if e["platform"] == "number":
            if e.get("min") is None or e.get("max") is None or e["min"] >= e["max"]:
                e["platform"] = "sensor"
                e.pop("min", None)
                e.pop("max", None)
            else:
                if e.get("multiplier"):
                    e["step"] = e["multiplier"]
                e["entity_category"] = "config"
        if "only readable" in desc or "nur lesbar" in desc:
            e["platform"] = "sensor"
            for k in ("min", "max", "step", "entity_category"):
                e.pop(k, None)
        e["_key"] = uniq(e["_key"])
        out.append(_entity("holding", e, source="doc"))
    for r in datapoints:
        if r["_addr"] in base_addr["input"]:
            continue
        e = PG.gen_datapoint(r)
        e["state_class"] = "measurement" if e.get("unit") else None
        e["_key"] = uniq(e["_key"])
        out.append(_entity("input", e, source="doc", internal=is_internal_pichler_dp(r.get("Name"))))
    return out


# --------------------------------------------------------------------------- #
# Dimplex (NWPM datapoint html): every table
# --------------------------------------------------------------------------- #
def dimplex_expansion(base_addr: dict[str, set]) -> tuple[list[dict], list[tuple]]:
    used: set[str] = set()

    def uniq(key: str) -> str:
        base, i = key or "reg", 2
        while key in used:
            key = f"{base}_{i}"
            i += 1
        used.add(key)
        return key

    out: list[dict] = []
    skipped: list[tuple] = []
    for r in sources.dimplex_datapoints():
        tbl, addr, name = r["table"], r["addr"], r["name"]
        if addr in base_addr[tbl]:
            continue
        if r["rw"] == "W":  # write-only (RTC-set block etc.) -> a manual button instead
            skipped.append((tbl, addr, name, "write-only"))
            continue
        if tbl == "coil" and re.match(r"\s*set ", name, re.I):
            skipped.append((tbl, addr, name, "write-only RTC dup"))
            continue
        typ = "float16" if "float" in (r["type"] or "").lower() else "uint16"
        u, dc, sc = unit_dc(r.get("unit"), name, name=name)
        e: dict = {"address": addr, "_key": uniq(PG.slug(name, addr)),
                   "_name": re.sub(r"\s+", " ", name).strip(), "type": typ}
        if u:
            e["unit"] = u
        if dc:
            e["device_class"] = dc
        if tbl == "input":
            e["platform"] = "sensor"
            if sc:
                e["state_class"] = sc
        elif tbl == "holding":
            mn, mx = r["min"], r["max"]
            if mn is None or mx is None or mn >= mx:
                e["platform"] = "sensor"
                e.pop("device_class", None)
                if sc:
                    e["state_class"] = sc
            else:
                e["platform"] = "number"
                e["min"], e["max"] = mn, mx
                if r.get("decimals"):
                    # Decimal bounds are display units over an integer register
                    # holding tenths (validated against register 47: its
                    # hand-modeled base entity is multiplier 0.1, 0.5..5.0 K).
                    e["multiplier"] = e["step"] = round(10 ** -r["decimals"], 6)
                e["entity_category"] = "config"
        elif tbl == "discrete":
            e["platform"] = "binary_sensor"
            for k in ("type", "unit", "device_class"):
                e.pop(k, None)
        elif tbl == "coil":
            e["platform"] = "switch"
            for k in ("type", "unit", "device_class"):
                e.pop(k, None)
        out.append(_entity(tbl, e, source="doc"))
    return out, skipped


def expansion(device_name: str, base_addr: dict[str, set]) -> tuple[list[dict], list[tuple]]:
    """All doc-generated entities for ``device_name`` not already in ``base_addr``."""
    if device_name == "Dimplex-SI-11TU":
        return dimplex_expansion(base_addr)
    return pichler_expansion(device_name, base_addr), []
