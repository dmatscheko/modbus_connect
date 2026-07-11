# ebyte ME31-AXAX404 — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## Digital inputs use the wrong Modbus object

The 4 digital inputs (ebyte_ip1..4) are modeled as **coils** (read via FC01) at
addresses 0–3, but the EBYTE manual documents them as **discrete inputs** (read
via FC02) at the same addresses. Same addresses, different object/function code.
If your unit doesn't answer FC01 for the inputs, move those four entities into a
`discrete:` section.

## Product code is truncated

The real product code is ME31-AXAX**4040** (4 relay outputs / 4 dry-contact
inputs); the device-file name `ME31-AXAX404` is a truncation.
