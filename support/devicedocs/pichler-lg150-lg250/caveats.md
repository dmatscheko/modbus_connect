# Pichler Lüftungsgerät LG 150 - LG 250 — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## Auto-generated expanded entities

Names come from the LS-Control workbook's English "Description" column; enums are
parsed from "(1=…, 2=…)" strings, so a register whose options aren't spelled out
in its name is exposed as a plain `number`, not a `select`.

## Scale columns are used inconsistently in the source

Scaling was verified to reproduce the existing hand-tuned entries, but note the
source uses its scale columns inconsistently (this file's Setpoints "Decimal"
column is a literal multiplier, not a decimal-place count) — keep this in mind if
you extend the file by hand.

## Raw internal registers

~27 `PIC_AD_*` / `Adc*` registers (rail voltages, raw ADC channels,
digital-input/relay states) are untagged and shown only via "Enable all
entities". They read raw counts and are diagnostic.

## Controller and address base

Requires the LS-Control **ES1015** controller with matching firmware. Register
addresses are the Modbus PDU (the workbook "Address" column is 1-based for
setpoints).
