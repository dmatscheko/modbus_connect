# Pichler Lüftungsgerät LG 150 - LG 250 — entity groups

**Device file:** `custom_components/modbus_connect/device_configs/pichler-lg150-lg250.yaml`

Entities are split into groups you can switch on/off on the integration's device page. `basic` is always on and never gets a switch; every other group gets an *Enable … entities* toggle. The **Enable all entities** master switch reveals everything, including untagged (expert) registers.

**Default groups (fresh install):** `basic`

**Total register + template entities:** 190

| Group | Tier | Switch on device page | Entities | Covers |
| --- | --- | --- | --- | --- |
| `basic` | core | (always on) | 44 | Everyday sensors, main controls and composite climate/fan entities. |
| `advanced` | tier | Enable Advanced entities | 62 | Miscellaneous extra settings that don't belong to a specific feature. |
| `modbus_config` | feature | Enable Modbus configuration entities | 4 | e.g. Modbus address, Modbus baud rate, Modbus parity, … |
| `co2_control` | feature | Enable CO2 control entities | 4 | e.g. CO2 KP, CO2 TI, CO2 cycle, … |
| `humidity_control` | feature | Enable Humidity control entities | 1 | e.g. Relative humidity maximum time in level 3 |
| `heat_exchanger` | feature | Enable Heat exchanger / bypass entities | 8 | e.g. Geothermal heat exchanger switching point summer, Geothermal heat exchanger switching point winter, Bypass switching point, … |
| `preheater` | feature | Enable Pre/post-heater entities | 10 | e.g. Post-heater, Internal post heater, Preheater control temperature, … |
| `defrost` | feature | Enable Defrost / frost entities | 9 | e.g. Defrost_On, Defrost time, Defrost pause, … |
| `external_sensors` | feature | Enable External sensors entities | 4 | e.g. External digital input E2, External digital input E2 - Ventilation level 3 stopping time, T2 internal to external compensation, … |
| `filter` | feature | Enable Filter entities | 2 | e.g. Filter time, Z16 Change filters |
| `fan_control` | feature | Enable Fan & flow entities | 16 | e.g. Supply fan stopping time, Mixing valve cycle time, Mixing valve running time, … |
| `firmware` | feature | Enable Firmware / model entities | 1 | e.g. Firmware Version Touch Display |
| *(untagged)* | expert | Enable all entities | 25 | Raw internal / diagnostic registers (rail & ADC readings, etc.). e.g. PIC_AD_T2, PIC_AD_T1, PIC_AD_0_10Vin_S1, … |

**Tiers:** *core* = `basic`, always shown · *tier* = `advanced`, broad opt-in · *feature* = one subsystem, toggle independently · *expert* = untagged, only via **Enable all entities**.

> Groups are OR-combined: an entity is shown when *any* of its groups is enabled. Hidden entities also drop out of the Modbus read plan (a shown template keeps its own source registers polled).
