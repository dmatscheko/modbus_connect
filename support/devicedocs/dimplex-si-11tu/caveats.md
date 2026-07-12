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
then edit. Both selects show "unknown" whenever the register holds a code
outside their documented options — after power-up (no selection made yet,
register reads 0), and on *Zeitfunktion Auswahl* also when a Smart-RTC room
controller uses register 5065 for its room addresses (codes 50–79, doc
section 6.1.2). An unknown select stays operable: pick an option to take
control.

## Heat-quantity counters (Wärmemenge), and no Umweltenergie

Each heat-quantity counter is published as **three** registers — a `1-4`, `5-8`
and `9-12` digit group (NWPM section 5.2, the `*` marks the "Beispiel
Wärmemengen*" info box). They are one number split across registers:
`total = (9-12 × 100 000 000) + (5-8 × 10 000) + (1-4)`. This file folds each
triplet into a single counter with `sum_scale: [1, 10000, 100000000]`, so you
get one clean `kWh` total per category — **Wärmemenge Heizung** (5096–5098),
**Warmwasser** (5099–5101) and **Schwimmbad** (5102–5104) — instead of nine
partial registers that each roll over into the next.

**Umweltenergie** (the ambient heat harvested = heat delivered − electrical
input) is **not available**: the NWPM datapoint list publishes no environmental
-energy register, and no electrical-energy or power-input counter either, so it
cannot be read or computed over Modbus. The heat pump shows it on its own
display only.

## Auto-generated expanded entities

The entities added beyond the curated core carry German names taken from the
NWPM datapoint list, qualified with their doc-section subsystem (2./3.
Heizkreis, 2.Wärmeerzeuger, Schwimmbad, Laufzeit/Modus). Their scaling and
addresses were verified against the existing hand-tuned entries. All of this
requires the optional NWPM / NWPM-Touch Modbus-TCP extension on the heat-pump
manager.

## "1. Heizkreis Temperatur" reads an undocumented register

Input register 27 is inherited from the hand-curated source config, but the
datapoint list has no entry for it in the address column this file follows
(WPM software J/L/M) — the *H-software* column lists 27 as Außentemperatur.
The circuit sensors the doc does name are R5 = 2. Heizkreis (register 9) and
R13 = 3. Heizkreis (register 10); there is no dedicated 1st-circuit sensor,
which is why this entity carries no R designation. If its readings track
"Außentemperatur (R1)" on your unit, register 27 is just mirroring the
outside temperature and the entity should be removed — please report.

## Some settings are plain numbers, not selects

A few holding settings are exposed as plain `number` entities because the
datapoint list gives a min/max but no value labels; a `select` with the real
option map would be nicer once the labels are known. (Where the doc *does*
list labels — the circuit selector 5082, the parallel shift 5086, the coded
cooling setpoint 5089, the time-function selector 5065 — proper selects and a
scaled temperature number are provided.)
