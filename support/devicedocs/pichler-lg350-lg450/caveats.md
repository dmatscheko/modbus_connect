# Pichler Lüftungsgerät LG 350 - LG 450 — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## Auto-generated expanded entities

Names come from the LS-Control workbook's English "Description" column; enums are
parsed from "(0=…, 1=…)" strings, so a register whose options aren't spelled out
in its name is exposed as a plain `number`, not a `select`.

## Scale columns are used inconsistently in the source

Scaling was verified to reproduce the existing hand-tuned entries, but note the
source uses its scale columns inconsistently (this file's Setpoints "Decimal"
column is a decimal-place count, unlike the LG150-250 file) — keep this in mind
if you extend the file by hand.

## Firmware-gated registers

The summer-night-cooling block (addresses 2202–2213) and the external
Modbus-sensor readings (5200-range) only exist and read meaningfully on firmware
≥ v1.6 and when those optional sensors/features are actually fitted; otherwise
they read 0 or the device NAKs them.

## Controller and address base

Requires the LS-Control **ES2020** controller (also covers LG740 / LG1000).
Register addresses are the Modbus PDU (the workbook "Address" column is 1-based
for setpoints).
