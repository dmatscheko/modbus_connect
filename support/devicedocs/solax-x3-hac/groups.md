# SolaX Power X3-HAC (11 kW) — entity groups

**Device file:** `custom_components/modbus_connect/device_configs/solax-x3-hac.yaml`

Entities are split into groups you can switch on/off on the integration's companion **Configuration** device. `basic` is always on and never gets a switch; every other group gets an *Enable … entities* toggle. The **Enable all entities** master switch reveals everything, including untagged (expert) registers.

**Default groups (fresh install):** `basic`, `standard`

**Total register + template entities:** 77

| Group | Kind | Switch on Configuration device | Entities | Covers |
| --- | --- | --- | --- | --- |
| `basic` | core | (always on) | 4 | Everyday essentials — main controls, headline sensors and the composite climate/fan entities. Always shown. |
| `standard` | tier | Enable Standard entities | 14 | The everyday set beyond the basics: common setpoints, secondary readings and totals. On by default. |
| `advanced` | tier | Enable Advanced entities | 59 | The full detail — deep settings, per-component diagnostics and secondary readings. |
| `charging` | feature | Enable Charging entities | 37 | e.g. Charger Use Mode, Start Charge Mode, Boost Mode, … |
| `grid` | feature | Enable Grid entities | 10 | e.g. Grid Current L1, Grid Current L2, Grid Current L3, … |
| `settings` | feature | Enable System settings entities | 13 | e.g. Meter Setting, ECO Gear, Green Gear, … |
| `diagnostics` | feature | Enable Diagnostics & identity entities | 14 | e.g. Device Lock, CC Voltage, CP Voltage, … |
| `modbus_config` | feature | Enable Modbus & comms entities | 3 | e.g. Sync RTC, Modbus Address, RTC |

**Kinds:** *core* = `basic`, always shown · *tier* = `standard` (on by default) and `advanced`, broad opt-in detail levels · *feature* = one functional group (subsystem), toggle independently · *expert* = untagged, only via **Enable all entities**.

> Groups are OR-combined: an entity is shown when *any* of its groups is enabled. Hidden entities also drop out of the Modbus read plan (a shown template keeps its own source registers polled).
