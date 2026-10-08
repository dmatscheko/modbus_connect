#!/usr/bin/env python3
"""Global orchestrator: regenerate every bundled device config.

    1. modbus_local_gateway  -> the ~19 MLG-derived configs (needs an upstream checkout)
    2. owned devices         -> Dimplex / Pichler / SolaX, straight from their
                                hand-maintained support/devicedocs/<slug>/device.yaml
    3. device docs           -> support/devicedocs/<slug>/registers.md + groups.md,
                                regenerated from the configs just written

The owned devices are no longer imported from the other projects: their source of
truth is an in-tree ``device.yaml`` (same format as the emitted config), run through
the shared augment library (``_common/augment.py``, the single writer) so every file
still lands in one canonical style. Only step 1 needs an external checkout. To
regenerate just one owned device (and its docs) without that checkout, pass
``--owned <slug>``.

    MLG_GATEWAY_REPO=/path/to/modbus_local_gateway \\
        python support/converter/convert_all.py

    python support/converter/convert_all.py --owned solax-x3-hac
"""
from __future__ import annotations

import argparse
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

# The device-doc generators (registers.md / groups.md), run after every config write.
sys.path.insert(0, str(_HERE / "_common"))
import build_groups_md  # noqa: E402
import build_registers_md  # noqa: E402

_DEFAULT_MLG = "/Users/dma/Eigenes/Development/home_assistant_projects/modbus_local_gateway"
_MLG_CONFIGS = (
    Path(os.environ.get("MLG_GATEWAY_REPO", _DEFAULT_MLG))
    / "custom_components/modbus_local_gateway/device_configs"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--owned",
        metavar="SLUG",
        help="regenerate only this owned device config (no upstream checkout required)",
    )
    args = parser.parse_args(argv)

    if args.owned:
        owned = augment.owned_slugs()
        if args.owned not in owned:
            parser.error(
                f"{args.owned!r} is not an owned device; choose one of: {', '.join(owned)}"
            )
        summary = augment.write_owned(args.owned, variant=__file__)
        print(f"{args.owned}: {summary}")
        _write_docs({args.owned})
        return 0

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
    for slug in augment.owned_slugs():
        summary = augment.write_owned(slug, variant=__file__)
        print(f"  {slug}: {summary}")

    _write_docs()
    print("\nAll device configs and docs regenerated (one canonical style via the augment library).")
    return 0


def _write_docs(only: set[str] | None = None) -> None:
    """Regenerate registers.md / groups.md from the configs just written."""
    print(f"\n{'=' * 8} device docs {'=' * 8}")
    build_registers_md.write_docs(only)
    build_groups_md.write_docs(only)


if __name__ == "__main__":
    sys.exit(main())
