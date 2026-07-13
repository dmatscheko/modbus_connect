# SolaX Power X3-Hybrid G4 — entity groups

**Device file:** `custom_components/modbus_connect/device_configs/solax-x3-hybrid-g4.yaml`

Entities are split into groups you can switch on/off on the integration's device page. `basic` is always on and never gets a switch; every other group gets an *Enable … entities* toggle. The **Enable all entities** master switch reveals everything, including untagged (expert) registers.

**Default groups (fresh install):** `basic`

**Total register + template entities:** 364

| Group | Tier | Switch on device page | Entities | Covers |
| --- | --- | --- | --- | --- |
| `basic` | core | (always on) | 28 | Everyday essentials — main controls, headline sensors and the composite climate/fan entities. Always shown. |
| `advanced` | tier | Enable Advanced entities | 104 | The full detail — deep settings, per-component diagnostics and secondary readings. |
| `pm_i1` | feature | Enable Parallel mode Inverter 1 entities | 22 | e.g. PM Inverter Count, PM ActivePower L1, PM ActivePower L2, … |
| `pm_i2` | feature | Enable Parallel mode Inverter 2 entities | 26 | e.g. PM Inverter Count, PM I2 ActivePower L1, PM I2 ActivePower L2, … |
| `pm_i3` | feature | Enable Parallel mode Inverter 3 entities | 26 | e.g. PM Inverter Count, PM I3 ActivePower L1, PM I3 ActivePower L2, … |
| `eps` | feature | Enable Eps entities | 22 | e.g. EPS Min SOC, EPS Restart SOC, EPS Mute, … |
| `generator` | feature | Enable Generator entities | 33 | e.g. Switch On SOC, Switch Off SOC, Minimum Per On Signal, … |
| `grid` | feature | Enable Grid entities | 14 | e.g. Grid Voltage, Grid Voltage L1, Grid Voltage L2, … |
| `grid_to_battery` | feature | Enable Grid to battery entities | 2 | e.g. E Charge Today, Grid to Battery Power |
| `home_consumption` | feature | Enable Home consumption entities | 2 | e.g. House load, Home Consumption Energy |
| `solar_details` | feature | Enable Solar details entities | 2 | e.g. PV Energy 1, PV Energy 2 |
| *(untagged)* | expert | Enable all entities | 100 | Raw internal / diagnostic registers (rail & ADC readings, etc.). e.g. Safety code, MateBox enabled, Battery Awaken, … |

**Tiers:** *core* = `basic`, always shown · *tier* = `standard` (on by default) and `advanced`, broad opt-in detail levels · *feature* = one subsystem, toggle independently · *expert* = untagged, only via **Enable all entities**.

> Groups are OR-combined: an entity is shown when *any* of its groups is enabled. Hidden entities also drop out of the Modbus read plan (a shown template keeps its own source registers polled).
