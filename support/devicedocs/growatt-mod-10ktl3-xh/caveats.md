# Growatt MOD 10KTL3-XH — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## Protocol document is community-hosted

The Modbus protocol document is manufacturer-authored but community-hosted (the
grott mirror) — Growatt does not publish it publicly.

## Verify the register base for your model

Verify the register base for your exact model: the doc names this one explicitly
as "MOD TL3-XH" (03: 0–124, 3000–3124; 04: 3000–3124, 3125–3249). Values are
big-endian / high-word-first.
