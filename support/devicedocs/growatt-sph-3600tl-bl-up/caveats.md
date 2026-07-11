# Growatt SPH3600TL BL_UP — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## Protocol document is community-hosted

The Modbus protocol document is manufacturer-authored but community-hosted (the
grott mirror) — Growatt does not publish it publicly.

## Verify the register base for your model

Verify the register base for your exact model: this SPH storage model uses the
1000-range block (input 1009–1041, holding 1044–1092) plus the base 0–124 group —
DIFFERENT from the TL-X/TL-XH models' 3000-range. Values are big-endian /
high-word-first.
