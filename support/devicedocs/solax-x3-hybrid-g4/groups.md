# SolaX Power X3-Hybrid G4 — entity groups

**Device file:** `custom_components/modbus_connect/device_configs/solax-x3-hybrid-g4.yaml`

Entities are split into groups you can switch on/off on the integration's device page. `basic` is always on and never gets a switch; every other group gets an *Enable … entities* toggle. The **Enable all entities** master switch reveals everything, including untagged (expert) registers.

**Default groups (fresh install):** `basic`, `standard`

**Total register + template entities:** 364

| Group | Tier | Switch on device page | Entities | Covers |
| --- | --- | --- | --- | --- |
| `basic` | core | (always on) | 6 | Everyday essentials — main controls, headline sensors and the composite climate/fan entities. Always shown. |
| `standard` | tier | Enable Standard entities | 27 | The everyday set beyond the basics: common setpoints, secondary readings and totals. On by default. |
| `advanced` | tier | Enable Advanced entities | 199 | The full detail — deep settings, per-component diagnostics and secondary readings. |
| `inverter` | feature | Enable Inverter entities | 22 | e.g. System On, System Off, Shut Down, … |
| `pv` | feature | Enable Solar PV entities | 17 | e.g. MPPT, Max PV Output Power, Shadow Fix Function Level PV2 (GMPPT), … |
| `battery` | feature | Enable Battery entities | 46 | e.g. Battery Charge Max Current, Battery Discharge Max Current, Battery Awaken, … |
| `grid` | feature | Enable Grid entities | 31 | e.g. Export Control User Limit, Pgrid Bias, Export Control Factory Limit, … |
| `meter` | feature | Enable Meter & CT entities | 22 | e.g. Measured power, Meter 1 Direction, Meter 2 Direction, … |
| `home_consumption` | feature | Enable House load entities | 3 | e.g. House load, House load alt, Home Consumption Energy |
| `eps` | feature | Enable EPS / backup entities | 22 | e.g. EPS Min SOC, EPS Restart SOC, EPS Mute, … |
| `generator` | feature | Enable Generator entities | 33 | e.g. Switch On SOC, Switch Off SOC, Minimum Per On Signal, … |
| `work_mode` | feature | Enable Work mode & schedule entities | 37 | e.g. Charger Use Mode, Manual Mode Select, Selfuse Discharge Min SOC, … |
| `remote_control` | feature | Enable Remote control (VPP) entities | 32 | e.g. Modbus Power Control (direct), RemoteControl Target Set Type (mode 8/9; direct), Remotecontrol Active Power (mode 1; direct), … |
| `settings` | feature | Enable System settings entities | 12 | e.g. Safety code, Main Breaker Current Limit, Phase Power Balance X3, … |
| `diagnostics` | feature | Enable Diagnostics & identity entities | 15 | e.g. Lock State, Manufacturer, Model Number, … |
| `modbus_config` | feature | Enable Modbus & comms entities | 8 | e.g. Sync RTC, MateBox enabled, Modbus Protocol Version, … |
| `pm_i1` | feature | Enable Parallel mode Inverter 1 entities | 22 | e.g. PM Inverter Count, PM ActivePower L1, PM ActivePower L2, … |
| `pm_i2` | feature | Enable Parallel mode Inverter 2 entities | 26 | e.g. PM Inverter Count, PM I2 ActivePower L1, PM I2 ActivePower L2, … |
| `pm_i3` | feature | Enable Parallel mode Inverter 3 entities | 26 | e.g. PM Inverter Count, PM I3 ActivePower L1, PM I3 ActivePower L2, … |
| `grid_to_battery` | feature | Enable Grid to battery entities | 2 | e.g. E Charge Today, Grid to Battery Power |
| `solar_details` | feature | Enable Solar details entities | 2 | e.g. PV Energy 1, PV Energy 2 |

**Tiers:** *core* = `basic`, always shown · *tier* = `standard` (on by default) and `advanced`, broad opt-in detail levels · *feature* = one subsystem, toggle independently · *expert* = untagged, only via **Enable all entities**.

> Groups are OR-combined: an entity is shown when *any* of its groups is enabled. Hidden entities also drop out of the Modbus read plan (a shown template keeps its own source registers polled).
