# Dimplex Sole/Wasser-Wärmepumpe SI 11TU — entity groups

**Device file:** `custom_components/modbus_connect/device_configs/dimplex-si-11tu.yaml`

Entities are split into groups you can switch on/off on the integration's device page. `basic` is always on and never gets a switch; every other group gets an *Enable … entities* toggle. The **Enable all entities** master switch reveals everything, including untagged (expert) registers.

**Default groups (fresh install):** `basic`

**Total register + template entities:** 128

| Group | Tier | Switch on device page | Entities | Covers |
| --- | --- | --- | --- | --- |
| `basic` | core | (always on) | 26 | Everyday sensors, main controls and composite climate/fan entities. |
| `advanced` | tier | Enable Advanced entities | 6 | Miscellaneous extra settings that don't belong to a specific feature. |
| `schedule` | feature | Enable Schedule / time program entities | 19 | e.g. Zeitfunktion Auswahl, Start Stunde 1, Start Minute 1, … |
| `clock` | feature | Enable Clock entities | 7 | e.g. Stunde, Minute, Monat, … |
| `heating_circuit_2` | feature | Enable Heating circuit 2 entities | 12 | e.g. 2./3. Heizkreis Auswahl, 2./3. Heizkreis Heizkurvenendpunkt, 2./3. Heizkreis Festwertemperatur, … |
| `heating_circuit_3` | feature | Enable Heating circuit 3 entities | 12 | e.g. 2./3. Heizkreis Auswahl, 2./3. Heizkreis Heizkurvenendpunkt, 2./3. Heizkreis Festwertemperatur, … |
| `heat_generator_2` | feature | Enable 2nd heat generator entities | 5 | e.g. 2.Wärmeerzeuger Mischerhysterese, 2.Wärmeerzeuger Grenztemperatur parallel, 2.Wärmeerzeuger Mischerlaufzeit, … |
| `pool` | feature | Enable Pool entities | 6 | e.g. Schwimmbad Hysterese, Schwimmbad Solltemperatur, Wärmemenge Schwimmbad, … |
| `cooling` | feature | Enable Cooling entities | 2 | e.g. Solltemp. dyn. Kühlung, 2./3. Heizkreis Kühlung Raumsolltemperatur |
| `solar` | feature | Enable Solar entities | 1 | e.g. Solarspeicher (R22) |
| `ventilation` | feature | Enable Ventilation entities | 6 | e.g. Außenlufttemperatur, Zulufttemperatur, Ablufttemperatur, … |
| `room_climate` | feature | Enable Room climate sensors entities | 4 | e.g. Raumtemperatur 1 / RT-RTH Econ, Raumtemperatur 2, Raumfeuchte 1 / RT-RTH Econ, … |
| `smart_grid` | feature | Enable Smart Grid entities | 4 | e.g. Smart Grid, Smart Grid 1, Smart Grid 2, … |
| `energy` | feature | Enable Energy & runtime entities | 9 | e.g. Verdichter 1 Laufzeit, Primärpumpe / Ventilator (M11) Laufzeit, Heizungspumpe (M13) Laufzeit, … |
| `heat_source` | feature | Enable Heat source (brine) entities | 1 | e.g. Rücklauftemp. gem. Primärkreis (R24) |
| `status` | feature | Enable Component status entities | 21 | e.g. Sperrmeldung, Sensorfehler, Warmwasserthermostat, … |

**Tiers:** *core* = `basic`, always shown · *tier* = `advanced`, broad opt-in · *feature* = one subsystem, toggle independently · *expert* = untagged, only via **Enable all entities**.

> Groups are OR-combined: an entity is shown when *any* of its groups is enabled. Hidden entities also drop out of the Modbus read plan (a shown template keeps its own source registers polled).
