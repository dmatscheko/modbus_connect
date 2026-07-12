#!/usr/bin/env python3
"""Global orchestrator: regenerate every bundled device config.

    1. modbus_local_gateway  -> the ~19 MLG-derived configs (needs an upstream checkout)
    2. owned devices         -> Dimplex / Pichler / SolaX, straight from their
                                hand-maintained support/devicedocs/<slug>/device.yaml

The owned devices are no longer imported from the other projects: their source of
truth is an in-tree ``device.yaml`` (same format as the emitted config), run through
the shared augment library (``_common/augment.py``, the single writer) so every file
still lands in one canonical style. Only step 1 needs an external checkout; edit an
owned device by editing its ``device.yaml`` and re-running this script.

    MLG_GATEWAY_REPO=/path/to/modbus_local_gateway \\
        python support/converter/convert_all.py
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_DEVICE_CONFIGS = _REPO / "custom_components/modbus_connect/device_configs"

# The shared augment library (single writer + the owned-device entry point).
_spec = importlib.util.spec_from_file_location("augment", _HERE / "_common" / "augment.py")
augment = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(augment)

_DEFAULT_MLG = "/Users/dma/Eigenes/Development/home_assistant_projects/modbus_local_gateway"
_MLG_CONFIGS = (
    Path(os.environ.get("MLG_GATEWAY_REPO", _DEFAULT_MLG))
    / "custom_components/modbus_local_gateway/device_configs"
)


def main() -> int:
    if not _MLG_CONFIGS.is_dir():
        print(f"modbus_local_gateway device_configs not found at {_MLG_CONFIGS}\n"
              f"set MLG_GATEWAY_REPO to your checkout.", file=sys.stderr)
        return 1

    print(f"\n{'=' * 8} modbus_local_gateway {'=' * 8}")
    subprocess.run([
        sys.executable, str(_HERE / "modbus_local_gateway" / "modbus_local_gateway-convert.py"),
        str(_MLG_CONFIGS), "-o", str(_DEVICE_CONFIGS),
    ], check=True)

    print(f"\n{'=' * 8} owned devices (device.yaml) {'=' * 8}")
    for slug in augment.OWNED_DEVICES:
        summary = augment.write_owned(slug, variant=__file__)
        print(f"  {slug}: {summary}")

    print("\nAll device configs regenerated (one canonical style via the augment library).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
