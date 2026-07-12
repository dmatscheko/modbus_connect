#!/usr/bin/env python3
"""Generate ``support/devicedocs/<device>/groups.md`` for every bundled device
config that uses entity groups (Dimplex, Pichler, SolaX).

The table lists every group, its tier/kind, the switch shown on the device page,
how many entities it holds, and what it covers — same format for all devices.

Run:  python3 build_groups_md.py            # all grouped devices
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_registers_md as R

TABLES = ("holding", "input", "coil", "discrete")

# Fixed descriptions for the tier groups; feature groups fall back to their label.
FIXED = {
    "basic": ("core", "Everyday sensors, main controls and composite climate/fan entities."),
    "advanced": ("tier", "Miscellaneous extra settings that don't belong to a specific feature."),
}
UNTAGGED = ("expert", "Raw internal / diagnostic registers (rail & ADC readings, etc.).")


def _switch_label(group: str, labels: dict) -> str:
    base = labels.get(group) or (group[:1].upper() + group[1:].replace("_", " "))
    return f"Enable {base} entities"


def _display_name(key: str, p: dict) -> str:
    return (p.get("ha") or {}).get("name") or key


def _scan(cfg: dict):
    counts: Counter = Counter()
    examples: dict[str, list[str]] = {}
    untagged = total = 0
    sections = [(cfg.get(t) or {}) for t in TABLES] + [cfg.get("template") or {}]
    for i, sec in enumerate(sections):
        for key, p in sec.items():
            if not isinstance(p, dict):
                continue
            # internal registers never become HA entities: no switch reveals
            # them, so they don't belong in any entity count.
            if i < len(TABLES) and ("address" not in p or p.get("internal")):
                continue
            total += 1
            for g in (p.get("groups") or ["*untagged*"]):
                counts[g] += 1
                if len(examples.setdefault(g, [])) < 3:
                    examples[g].append(_display_name(key, p))
            if not p.get("groups"):
                untagged += 1
    return counts, untagged, total, examples


def gen_one(cfg_name: str, folder: str) -> str | None:
    cfg = yaml.safe_load((R.CFG_DIR / cfg_name).read_text())
    dev = cfg.get("device", {})
    labels = dev.get("group_labels", {}) or {}
    default = dev.get("default_groups")
    counts, untagged, total, examples = _scan(cfg)
    feat_counts = {g: n for g, n in counts.items() if g != "*untagged*"}
    if not feat_counts:
        return None   # config doesn't use groups

    # order: basic, advanced, feature groups (group_labels order, then alphabetical)
    order = [g for g in ("basic", "advanced") if g in counts]
    feats = [g for g in counts if g not in ("basic", "advanced", "*untagged*")]
    lab_order = [g for g in labels if g in feats]
    order += lab_order + sorted(g for g in feats if g not in lab_order)

    def eg(g):
        names = examples.get(g, [])
        return "e.g. " + ", ".join(names) + (", …" if counts[g] > len(names) else "") if names else "—"

    rows = []
    for g in order:
        if g in FIXED:
            kind, desc = FIXED[g]
            switch = "(always on)" if g == "basic" else _switch_label(g, labels)
        else:
            kind, desc = "feature", eg(g)
            switch = _switch_label(g, labels)
        rows.append((f"`{g}`", kind, switch, counts[g], desc))
    if untagged:
        rows.append(("*(untagged)*", UNTAGGED[0], "Enable all entities", untagged,
                     f"{UNTAGGED[1]} {eg('*untagged*')}"))

    manuf, model = dev.get("manufacturer", ""), dev.get("model", "")
    default_txt = ", ".join(f"`{g}`" for g in default) if default else "*(unset — every group shown)*"
    out = [
        f"# {manuf} {model} — entity groups", "",
        f"**Device file:** `custom_components/modbus_connect/device_configs/{cfg_name}`", "",
        "Entities are split into groups you can switch on/off on the integration's "
        "device page. `basic` is always on and never gets a switch; every other group "
        "gets an *Enable … entities* toggle. The **Enable all entities** master switch "
        "reveals everything, including untagged (expert) registers.", "",
        f"**Default groups (fresh install):** {default_txt}", "",
        f"**Total register + template entities:** {total}", "",
        "| Group | Tier | Switch on device page | Entities | Covers |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, kind, switch, n, desc in rows:
        out.append(f"| {name} | {kind} | {switch} | {n} | {desc} |")
    out += [
        "", "**Tiers:** *core* = `basic`, always shown · *tier* = `advanced`, broad "
        "opt-in · *feature* = one subsystem, toggle independently · *expert* = untagged, "
        "only via **Enable all entities**.", "",
        "> Groups are OR-combined: an entity is shown when *any* of its groups is enabled. "
        "Hidden entities also drop out of the Modbus read plan (a shown template keeps its "
        "own source registers polled).", "",
    ]
    return "\n".join(out)


def main() -> None:
    only = set(sys.argv[1:]) if len(sys.argv) > 1 else None
    for cfg_name, folder in R.CONFIG_TO_FOLDER.items():
        if folder in R.DOC_EXCLUDED:
            continue
        if only and folder not in only:
            continue
        md = gen_one(cfg_name, folder)
        if md is None:
            continue
        dest = R.OUT_DIR / folder
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "groups.md").write_text(md, encoding="utf-8")
        print(f"wrote {folder}/groups.md")


if __name__ == "__main__":
    main()
