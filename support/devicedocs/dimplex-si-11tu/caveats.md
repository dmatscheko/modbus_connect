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

## Two multiplexed setting blocks

The WPM edits some settings through *multiplexers* (NWPM doc sections 5.3.2
and 5.4):

- **2./3. heating circuit** (registers 5084–5089 and 93): the *2./3. Heizkreis
  Auswahl* select (register 5082) picks circuit 2 or 3; the seven
  "2./3. Heizkreis …" settings then read **and write** whichever circuit is
  selected.
- **Time functions** (registers 5066–5081): the *Zeitfunktion Auswahl* select
  (register 5065) picks which function — setback/boost per circuit, hot-water
  block, thermal disinfection, circulation pump — the schedule times, weekday
  flags, and the setback/boost value belong to.

The integration shows one set of entities per block: the values of the active
selection. Switch the select first, wait one poll cycle so the block re-reads,
then edit. After power-up the selects may show "unknown" until a selection is
first written (the device can report a code outside the documented options).

## Auto-generated expanded entities

The entities added beyond the curated core carry German names taken from the
NWPM datapoint list, qualified with their doc-section subsystem (2./3.
Heizkreis, 2.Wärmeerzeuger, Schwimmbad, Laufzeit/Modus). Their scaling and
addresses were verified against the existing hand-tuned entries. All of this
requires the optional NWPM / NWPM-Touch Modbus-TCP extension on the heat-pump
manager.

## Some settings are plain numbers, not selects

A few holding settings are exposed as plain `number` entities because the
datapoint list gives a min/max but no value labels; a `select` with the real
option map would be nicer once the labels are known. (Where the doc *does*
list labels — the circuit selector 5082, the parallel shift 5086, the coded
cooling setpoint 5089, the time-function selector 5065 — proper selects and a
scaled temperature number are provided.)
