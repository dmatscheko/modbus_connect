#!/usr/bin/env python3
"""Global orchestrator: regenerate every bundled device config, in the order that
lets the specialized importers win.

    1. modbus_local_gateway  -> the ~19 MLG-derived configs (skips Dimplex/Pichler)
    2. dimplex_pichler       -> overwrites Dimplex/Pichler with their enriched configs
    3. solax                 -> the two SolaX inverter configs

Order matters: the modbus_local_gateway source also contains the Dimplex/Pichler base
files, but those three are owned by the dimplex_pichler importer (base + documented
extras + composite templates), so step 1 skips them and step 2 writes the full version.

Every converter emits through the shared augment library (``_common/augment.py``), the
single writer, so all files land in one canonical style.

Point the two upstream checkouts at your local clones (defaults assume they sit beside
this repo):

    MLG_GATEWAY_REPO=/path/to/modbus_local_gateway \\
    SOLAX_MODBUS_REPO=/path/to/homeassistant-solax-modbus \\
        python support/converter/convert_all.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_DEVICE_CONFIGS = _REPO / "custom_components/modbus_connect/device_configs"

_DEFAULT_MLG = "/Users/dma/Eigenes/Development/home_assistant_projects/modbus_local_gateway"
_MLG_CONFIGS = (
    Path(os.environ.get("MLG_GATEWAY_REPO", _DEFAULT_MLG))
    / "custom_components/modbus_local_gateway/device_configs"
)


def _step(name: str, argv: list[str]) -> None:
    print(f"\n{'=' * 8} {name} {'=' * 8}")
    subprocess.run(argv, check=True)


def main() -> int:
    if not _MLG_CONFIGS.is_dir():
        print(f"modbus_local_gateway device_configs not found at {_MLG_CONFIGS}\n"
              f"set MLG_GATEWAY_REPO to your checkout.", file=sys.stderr)
        return 1
    _step("modbus_local_gateway", [
        sys.executable, str(_HERE / "modbus_local_gateway" / "modbus_local_gateway-convert.py"),
        str(_MLG_CONFIGS), "-o", str(_DEVICE_CONFIGS),
    ])
    _step("dimplex_pichler", [
        sys.executable, str(_HERE / "dimplex_pichler" / "dimplex_pichler-convert.py"),
    ])
    _step("solax", [
        sys.executable, str(_HERE / "solax" / "homeassistant_solax_modbus-convert.py"),
    ])
    print("\nAll device configs regenerated (one canonical style via the augment library).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
