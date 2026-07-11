#!/usr/bin/env python3
"""Regenerate the Dimplex and Pichler device configs from source.

Two mechanical sources are merged in memory:

  1. the ``modbus_local_gateway`` upstream config for the device (the curated base
     entity set), converted with the MLG converter — this gives the nicely-named
     "basic" registers with their icons and HA metadata; and
  2. the manufacturer's own Modbus document (Pichler LS-Control ``.xlsx`` / Dimplex
     NWPM ``.html`` under ``support/devicedocs/``), which fills in every documented
     register the base does not already cover (see :mod:`dimplex_pichler_gen`).

Every entity is stamped with the *facts* a rule might need (its raw source name, its
unit, whether it is a raw internal reading, which source it came from). Everything
else — grouping, the composite climate/fan templates, the Dimplex *Sync clock*
button, per-entity overrides — is *policy* and lives in
``support/devicedocs/<slug>/augment.yaml``, applied by :func:`augment.write_augmented`.

The MLG upstream checkout is found via ``$MLG_GATEWAY_REPO`` (default: a
``modbus_local_gateway`` checkout beside this repo), the same source the MLG
converter uses.

    MLG_GATEWAY_REPO=/path/to/modbus_local_gateway \
        python support/converter/dimplex_pichler/dimplex_pichler-convert.py
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve()
_CONVERTER = _HERE.parents[1]
_REPO = _HERE.parents[3]


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


augment = _load("augment", _CONVERTER / "_common" / "augment.py")
_mlg = _load("mlg_convert", _CONVERTER / "modbus_local_gateway" / "modbus_local_gateway-convert.py")
sys.path.insert(0, str(_CONVERTER / "_common"))
import dimplex_pichler_gen as gen  # noqa: E402

DEVICES = ["Dimplex-SI-11TU", "Pichler-LG150-LG250", "Pichler-LG350-LG450"]


def _upstream_dir() -> Path:
    """Locate the modbus_local_gateway device_configs directory (the base source)."""
    root = os.environ.get("MLG_GATEWAY_REPO") or str(_REPO.parent / "modbus_local_gateway")
    path = Path(root)
    if path.name != "device_configs":
        path = path / "custom_components" / "modbus_local_gateway" / "device_configs"
    if not path.is_dir():
        raise SystemExit(
            f"modbus_local_gateway device_configs not found at {path}\n"
            "Set MLG_GATEWAY_REPO to a modbus_local_gateway checkout."
        )
    return path


def build_intermediate(device_name: str, upstream_dir: Path) -> dict:
    """MLG upstream base + manufacturer-doc expansion -> one tagged intermediate."""
    old = yaml.safe_load((upstream_dir / f"{device_name}.yaml").read_text(encoding="utf-8"))
    base = _mlg.convert_device(old, f"{device_name}.yaml")

    ir = augment.intermediate(base.get("device") or {})
    base_addr = {t: set() for t in gen.TABLES}
    for table in gen.TABLES:
        for key, fields in (base.get(table) or {}).items():
            fields = {k: v for k, v in fields.items() if k != "groups"}
            base_addr[table].add(fields["address"])
            ha = fields.get("ha") or {}
            raw_name = ha.get("name") or key
            tags = {f"raw-name:{raw_name}", "source:mlg"}
            if ha.get("unit_of_measurement"):
                tags.add(f"unit:{ha['unit_of_measurement']}")
            augment.add_entity(ir, table, key, tags=tags, **fields)

    expansion, skipped = gen.expansion(device_name, base_addr)
    for e in expansion:
        augment.add_entity(ir, e["table"], e["key"], tags=e["tags"], **e["fields"])
    return ir, skipped


def run() -> None:
    upstream_dir = _upstream_dir()
    for name in DEVICES:
        ir, skipped = build_intermediate(name, upstream_dir)
        summary = augment.write_augmented(
            ir, name, source="modbus_local_gateway base + manufacturer Modbus doc", variant=__file__
        )
        note = f"  (skipped {len(skipped)} write-only source rows)" if skipped else ""
        print(f"  {name}: {summary}{note}")


if __name__ == "__main__":
    sys.exit(run())
