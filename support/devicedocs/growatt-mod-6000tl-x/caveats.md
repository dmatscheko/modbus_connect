# Growatt MOD 6000TL-X — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## Protocol document is community-hosted

The Modbus protocol document is manufacturer-authored but community-hosted (the
grott mirror) — Growatt does not publish it publicly.

## Verify the register base for your model

Verify the register base for your exact model: this three-phase model uses the
3000-range input block (the same "TL-X and TL-XH" group as MOD TL3-XH), NOT the
separate "TL3-X (MAX/MID/MAC)" 0–249 layout. Values are big-endian /
high-word-first.
