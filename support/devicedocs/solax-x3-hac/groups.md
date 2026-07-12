# SolaX Power X3-HAC (11 kW) — entity groups

**Device file:** `custom_components/modbus_connect/device_configs/solax-x3-hac.yaml`

Entities are split into groups you can switch on/off on the integration's device page. `basic` is always on and never gets a switch; every other group gets an *Enable … entities* toggle. The **Enable all entities** master switch reveals everything, including untagged (expert) registers.

**Default groups (fresh install):** `basic`

**Total register + template entities:** 77

| Group | Tier | Switch on device page | Entities | Covers |
| --- | --- | --- | --- | --- |
| `basic` | core | (always on) | 9 | Everyday sensors, main controls and composite climate/fan entities. |
| `advanced` | tier | Enable Advanced entities | 37 | Miscellaneous extra settings that don't belong to a specific feature. |
| *(untagged)* | expert | Enable all entities | 31 | Raw internal / diagnostic registers (rail & ADC readings, etc.). e.g. Charge Phase Alt, Charge PE Voltage, Charge PE Current, … |

**Tiers:** *core* = `basic`, always shown · *tier* = `advanced`, broad opt-in · *feature* = one subsystem, toggle independently · *expert* = untagged, only via **Enable all entities**.

> Groups are OR-combined: an entity is shown when *any* of its groups is enabled. Hidden entities also drop out of the Modbus read plan (a shown template keeps its own source registers polled).
