# Anhui QDF70B Pressure Sensor — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## The unit and scaling are the sensor's factory setting, not read from it

The transmitter reports the measured value (register 4) as a signed 16-bit
integer whose meaning depends on two setup registers: the **unit** (register 2,
an enum from MPa to °F) and the **decimal places** (register 3, 0–4). Both are
read-only over Modbus, so they are fixed per unit at the factory. The device file
hard-codes **Pa with 0 decimals** — the configuration of the QDF70B it was tested
with. A sensor ordered in kPa or bar, or with decimals, shows the wrong unit and
magnitude in the `Pressure` entity; check the `Pressure unit` and `Decimal
places` diagnostics after adding the device and adapt a copy of the file if they
differ (`multiplier: 0.1` per decimal place, and the matching `unit`).

The float32 copy (`Pressure (float)`, registers 22–23, IEEE 754 big-endian)
already carries the decimal scaling, so its magnitude is right regardless of the
decimal setting; only its unit label follows the same assumption.

## Range points and zero offset are in raw value units

`Range zero point`, `Range full point` and `Zero offset` (registers 5, 6 and 12)
are documented as plain signed integers and are shown in the same unit as the
integer pressure reading (Pa, no scaling). The zero offset is added to the
calibrated measurement (`output = calibration value + zero offset`), so it is the
one user-side calibration knob the vendor allows; the calibration data itself is
locked (writes return an exception code) and needs the vendor's tool.

## Communication settings only persist after "Save settings"

Modbus address, baud rate, parity and zero offset are written into RAM; the
`Save settings` button (register 15, write 0) stores them. Changing the address
or baud rate takes effect right after the reply, so the integration loses the
device until the entry is reconfigured to match. `Restore factory settings`
(register 16, write 1) reloads the factory set, which the vendor warns may
differ from what was last saved (address, baud rate and calibration included) —
re-scan afterwards. Both buttons are opt-in under the *Modbus & comms* switch.

## Parity codes are inconsistent in the document

The protocol lists the parity register (0x0025) with a value range of 0–2 but
labels the options 1 = none, 2 = odd, 3 = even, while its own write example
writes 0. The file follows the range and the example (0 = none, 1 = odd,
2 = even). Verify on your unit before relying on the select.

## Holding register 9 is served but undocumented

The device answers reads of holding register 9 (found by the Modbus scanner)
but the protocol document does not list any register between the range full
point (6) and the zero offset (12). It is kept as the opt-in `Undocumented
register 9` diagnostic; please report what it tracks on your unit.

## Reads are split around the undocumented gap

The used registers span 0–12, 22–23 and 37. `max_read_gap: 8` lets the
integration bridge the small holes but not the 24–36 run, so an unimplemented
register in that gap cannot make a whole poll fail. The parity register is read
in its own request.
