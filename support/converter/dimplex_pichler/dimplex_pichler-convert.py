#!/usr/bin/env python3
"""Re-augment the Dimplex and Pichler device configs through the common library.

These three files are modbus_local_gateway-derived and then hand-curated (composite
climate templates, tuned setpoints, the documented extra registers, the Dimplex
*Sync clock* button). All of that is *content* and lives in the bundled config. The
only *policy* — which entity belongs to which group — lives in
``support/converter/<device>/augment.yaml``.

This "per-device part" simply reads each config as its content source, tags every
entity with the facts a grouping rule needs (its raw name, its table, whether it is a
raw internal reading), drops the existing group assignments, and hands the result to
:func:`augment.write_augmented`, which re-derives the groups from the augment.yaml and
rewrites the file in the one canonical style. Running it is an idempotent fixpoint.

    python support/converter/dimplex_pichler/dimplex_pichler-convert.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve()
_COMMON = _HERE.parents[1] / "_common"
_spec = importlib.util.spec_from_file_location("augment", _COMMON / "augment.py")
augment = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(augment)

_DEVICE_CONFIGS = _HERE.parents[3] / "custom_components/modbus_connect/device_configs"

# (config basename, family). The family only decides raw-internal detection.
DEVICES = ["Dimplex-SI-11TU", "Pichler-LG150-LG250", "Pichler-LG350-LG450"]

# device-level keys that are grouping *policy* (re-applied from augment.yaml), not content.
_POLICY_DEVICE_KEYS = ("default_groups", "group_labels")


def config_to_intermediate(doc: dict) -> dict:
    """A committed device config -> a tagged intermediate (grouping stripped).

    Only *facts* are stamped: the raw name a rule matches on, the table, the platform.
    All policy — including which entities are raw internals (expert tier) — is decided
    by the augment.yaml, so this stays device-agnostic."""
    device = {k: v for k, v in (doc.get("device") or {}).items() if k not in _POLICY_DEVICE_KEYS}
    ir = augment.intermediate(device)
    for table in augment.TABLES:
        for key, fields in (doc.get(table) or {}).items():
            fields = dict(fields)
            fields.pop("groups", None)
            name = (fields.get("ha") or {}).get("name") or key
            tags = {f"raw-name:{name}", f"table:{table}"}
            if fields.get("ha", {}).get("platform"):
                tags.add(f"platform:{fields['ha']['platform']}")
            augment.add_entity(ir, table, key, tags=tags, **fields)
    for key, fields in (doc.get("template") or {}).items():
        fields = dict(fields)
        fields.pop("groups", None)
        name = (fields.get("ha") or {}).get("name") or key
        augment.add_entity(ir, "template", key, tags={f"raw-name:{name}"}, **fields)
    return ir


def run() -> None:
    for name in DEVICES:
        doc = yaml.safe_load((_DEVICE_CONFIGS / f"{name}.yaml").read_text(encoding="utf-8"))
        dev = doc.get("device") or {}
        ir = config_to_intermediate(doc)
        header = (
            f"{dev.get('manufacturer', '')} {dev.get('model', '')} — "
            f"modbus_local_gateway-derived; entity groups from "
            f"support/converter/{name}/augment.yaml"
        ).strip()
        summary = augment.write_augmented(ir, name, header=header)
        print(f"  {name}: {summary}")


if __name__ == "__main__":
    sys.exit(run())
