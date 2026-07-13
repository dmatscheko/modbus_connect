# Dimplex Sole/Wasser-Wärmepumpe SI 11TU — entity groups

**Device file:** `custom_components/modbus_connect/device_configs/dimplex-si-11tu.yaml`

Entities are split into groups you can switch on/off on the integration's companion **Configuration** device. `basic` is always on and never gets a switch; every other group gets an *Enable … entities* toggle. The **Enable all entities** master switch reveals everything, including untagged (expert) registers.

**Default groups (fresh install):** `basic`, `standard`

**Total register + template entities:** 128

| Group | Kind | Switch on Configuration device | Entities | Covers |
| --- | --- | --- | --- | --- |
| `basic` | core | (always on) | 10 | Everyday essentials — main controls, headline sensors and the composite climate/fan entities. Always shown. |
| `standard` | tier | Enable Standard entities | 18 | The everyday set beyond the basics: common setpoints, secondary readings and totals. On by default. |
| `advanced` | tier | Enable Advanced entities | 27 | The full detail — deep settings, per-component diagnostics and secondary readings. |
| `operation` | feature | Enable Operation & mode entities | 5 | e.g. Betriebsmodus, Softwaresperre Extern, Anzahl Partystunden, … |
| `heating` | feature | Enable Heating circuit 1 entities | 11 | e.g. Heizung Parallelverschiebung, Heizung Raumtemperatur, Heizung Heizkurvenendpunkt, … |
| `hot_water` | feature | Enable Hot water circuit entities | 6 | e.g. Warmwasser Hysterese, Warmwasser Solltemperatur Minimal, Warmwasser Solltemperatur Maximal, … |
| `status` | feature | Enable Component status entities | 24 | e.g. Statusmeldung, Sperrmeldung, Störmeldung, … |
| `energy` | feature | Enable Energy & runtime entities | 12 | e.g. Verdichter 1 Laufzeit, Primärpumpe / Ventilator (M11) Laufzeit, Heizungspumpe (M13) Laufzeit, … |
| `heat_source` | feature | Enable Heat source (brine) entities | 3 | e.g. Wärmequelleneintrittstemperatur (R24), Wärmequellenaustrittstemperatur (R6), Rücklauftemp. gem. Primärkreis (R24) |
| `heating_circuit_2` | feature | Enable Heating circuit 2 entities | 12 | e.g. 2./3. Heizkreis Auswahl, 2./3. Heizkreis Heizkurvenendpunkt, 2./3. Heizkreis Festwertemperatur, … |
| `heating_circuit_3` | feature | Enable Heating circuit 3 entities | 12 | e.g. 2./3. Heizkreis Auswahl, 2./3. Heizkreis Heizkurvenendpunkt, 2./3. Heizkreis Festwertemperatur, … |
| `heat_generator_2` | feature | Enable 2nd heat generator entities | 5 | e.g. 2.Wärmeerzeuger Mischerhysterese, 2.Wärmeerzeuger Grenztemperatur parallel, 2.Wärmeerzeuger Mischerlaufzeit, … |
| `pool` | feature | Enable Pool entities | 6 | e.g. Schwimmbad Hysterese, Schwimmbad Solltemperatur, Wärmemenge Schwimmbad, … |
| `cooling` | feature | Enable Cooling entities | 4 | e.g. Solltemp. dyn. Kühlung, 2./3. Heizkreis Kühlung Raumsolltemperatur, Vorlauftemperatur (R11), … |
| `solar` | feature | Enable Solar entities | 1 | e.g. Solarspeicher (R22) |
| `ventilation` | feature | Enable Ventilation entities | 7 | e.g. Zeitwert Stoßlüften, Außenlufttemperatur, Zulufttemperatur, … |
| `room_climate` | feature | Enable Room climate sensors entities | 4 | e.g. Raumtemperatur 1 / RT-RTH Econ, Raumtemperatur 2, Raumfeuchte 1 / RT-RTH Econ, … |
| `smart_grid` | feature | Enable Smart Grid entities | 4 | e.g. Smart Grid, Smart Grid 1, Smart Grid 2, … |
| `schedule` | feature | Enable Schedule / time program entities | 19 | e.g. Zeitfunktion Auswahl, Start Stunde 1, Start Minute 1, … |
| `clock` | feature | Enable Clock entities | 7 | e.g. Stunde, Minute, Monat, … |
| `test` | feature | Enable Test entities | 1 | e.g. TEST What is this |

**Kinds:** *core* = `basic`, always shown · *tier* = `standard` (on by default) and `advanced`, broad opt-in detail levels · *feature* = one functional group (subsystem), toggle independently · *expert* = untagged, only via **Enable all entities**.

> Groups are OR-combined: an entity is shown when *any* of its groups is enabled. Hidden entities also drop out of the Modbus read plan (a shown template keeps its own source registers polled).
