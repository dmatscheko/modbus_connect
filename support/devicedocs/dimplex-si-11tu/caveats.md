# Dimplex Sole/Wasser-Wärmepumpe SI 11TU — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## Clock sync is best-effort

The "Sync clock" button writes the six clock value-registers 5006–5011 in one
FC16 write. The WPM also exposes write-only "set" strobe coils 102–107 (one per
field) that may be required to *commit* each value. One button can write the
value registers OR pulse the coils, not both — so if your WPM only applies the
clock after the strobe, the button loads the values but they won't take effect
until the coils are pulsed. The six strobe coils are intentionally not exposed.
A true one-click sync for this mechanism would need a new feature (a
button/action that performs a *sequence* of writes across registers and coils).
Verify on hardware.

## Auto-generated expanded entities

The ~78 entities added beyond the curated core have German names taken verbatim
from the NWPM datapoint list; some are terse. Their scaling and addresses were
verified against the existing hand-tuned entries. All of this requires the
optional NWPM / NWPM-Touch Modbus-TCP extension on the heat-pump manager.

## Some settings are plain numbers, not selects

A few holding settings are exposed as plain `number` entities because the
datapoint list gives a min/max but no value labels; a `select` with the real
option map would be nicer once the labels are known.
