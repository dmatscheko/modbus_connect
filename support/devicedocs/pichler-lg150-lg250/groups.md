# Pichler Lüftungsgerät LG 150 - LG 250 — entity groups

**Device file:** `custom_components/modbus_connect/device_configs/pichler-lg150-lg250.yaml`

Entities are split into groups you can switch on/off on the integration's companion **Configuration** device. `basic` is always on and never gets a switch; every other group gets an *Enable … entities* toggle. The **Enable all entities** master switch reveals everything, including untagged (expert) registers.

**Default groups (fresh install):** `basic`, `standard`

**Total register + template entities:** 190

| Group | Kind | Switch on Configuration device | Entities | Covers |
| --- | --- | --- | --- | --- |
| `basic` | core | (always on) | 10 | Everyday essentials — main controls, headline sensors and the composite climate/fan entities. Always shown. |
| `standard` | tier | Enable Standard entities | 23 | The everyday set beyond the basics: common setpoints, secondary readings and totals. On by default. |
| `advanced` | tier | Enable Advanced entities | 121 | The full detail — deep settings, per-component diagnostics and secondary readings. |
| `ventilation` | feature | Enable Ventilation & airflow entities | 16 | e.g. Betriebsmodus Sommer/Winter, Lüftungsstufe, Luftstrom Lüftungsstufe 1, … |
| `fan_control` | feature | Enable Fans entities | 24 | e.g. Supply fan stopping time, Mixing valve cycle time, Mixing valve running time, … |
| `temperatures` | feature | Enable Air temperatures entities | 21 | e.g. Temperaturregelungsart, Soll Zulufttemperatur, Soll Raumlufttemperatur, … |
| `heat_exchanger` | feature | Enable Heat exchanger / bypass entities | 10 | e.g. Geothermal heat exchanger switching point summer, Geothermal heat exchanger switching point winter, Bypass switching point, … |
| `preheater` | feature | Enable Pre/post-heater entities | 12 | e.g. Post-heater, Heating KP, Heating TI, … |
| `defrost` | feature | Enable Defrost / frost entities | 9 | e.g. Defrost on, Defrost time, Defrost pause, … |
| `faults` | feature | Enable Faults & alerts entities | 22 | e.g. Clear error log, Z01 T difference GHX, Z02 Operating panel, … |
| `filter` | feature | Enable Filter entities | 5 | e.g. Filter zurücksetzen, Filter später erinnern, Filter time, … |
| `co2_control` | feature | Enable CO2 control entities | 8 | e.g. CO2 Regelung, CO2 Maximum, CO2 KP, … |
| `humidity_control` | feature | Enable Humidity control entities | 5 | e.g. Luftfeuchtigkeit Regelung, Luftfeuchtigkeit Maximum, Relative humidity maximum time in level 3, … |
| `external_sensors` | feature | Enable External sensors entities | 3 | e.g. External digital input E2, External digital input E2 - Ventilation level 3 stopping time, T2 internal to external compensation |
| `controller` | feature | Enable Controller I/O (raw) entities | 36 | e.g. Configuration, Sensor configuration, Test mode, … |
| `modbus_config` | feature | Enable Modbus configuration entities | 4 | e.g. Modbus address, Modbus baud rate, Modbus parity, … |
| `firmware` | feature | Enable Firmware / model entities | 12 | e.g. Summer/Winter Time change, AHU Type, Firmware Version Touch Display, … |
| `system` | feature | Enable System & maintenance entities | 3 | e.g. Powersave at Standby, Reset to factory settings, Reset operating hours counter |

**Kinds:** *core* = `basic`, always shown · *tier* = `standard` (on by default) and `advanced`, broad opt-in detail levels · *feature* = one functional group (subsystem), toggle independently · *expert* = untagged, only via **Enable all entities**.

> Groups are OR-combined: an entity is shown when *any* of its groups is enabled. Hidden entities also drop out of the Modbus read plan (a shown template keeps its own source registers polled).
