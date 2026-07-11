# Growatt MIC 2500TL-X — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## Protocol document is community-hosted

The Modbus protocol document is manufacturer-authored but community-hosted (the
widely-referenced grott mirror) — Growatt does not publish it publicly.

## Verify the register base for your model

One protocol document covers the whole inverter family; verify the register base
for your exact model. This model reads from the 3000-range input block. Values
are big-endian / high-word-first.
