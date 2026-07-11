# Growatt MIN 6000TL-XH — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## Protocol document is community-hosted

The Modbus protocol document is manufacturer-authored but community-hosted (the
grott mirror) — Growatt does not publish it publicly.

## Verify the register base for your model

Verify the register base for your exact model: this TL-XH storage model uses the
3000-range input block plus a storage extension (3125–3249), and its storage
settings live in the 3000-range holding (not the 1000-range). Values are
big-endian / high-word-first.
