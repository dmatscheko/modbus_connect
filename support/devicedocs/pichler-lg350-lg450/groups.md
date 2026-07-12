# Pichler Lüftungsgerät LG 350 - LG 450 — entity groups

**Device file:** `custom_components/modbus_connect/device_configs/pichler-lg350-lg450.yaml`

Entities are split into groups you can switch on/off on the integration's device page. `basic` is always on and never gets a switch; every other group gets an *Enable … entities* toggle. The **Enable all entities** master switch reveals everything, including untagged (expert) registers.

**Default groups (fresh install):** `basic`

**Total register + template entities:** 187

| Group | Tier | Switch on device page | Entities | Covers |
| --- | --- | --- | --- | --- |
| `basic` | core | (always on) | 132 | Everyday sensors, main controls and composite climate/fan entities. |
| `advanced` | tier | Enable Advanced entities | 22 | Miscellaneous extra settings that don't belong to a specific feature. |
| `modbus_config` | feature | Enable Modbus configuration entities | 14 | e.g. Modbus address, Modbus baudrate, Modbus parity, … |
| `co2_control` | feature | Enable CO2 control entities | 3 | e.g. EPB CO2, EPB CO2 Regulation, Current CO2 control value |
| `humidity_control` | feature | Enable Humidity control entities | 1 | e.g. Relative humidity setpoint Winter |
| `summer_night_cooling` | feature | Enable Summer-night cooling entities | 4 | e.g. Sommernacht Kühlung Status, Sommernacht Kühlung Testzeit, Sommernacht Kühlung Wiederholungszeit, … |
| `preheater` | feature | Enable Pre/post-heater entities | 4 | e.g. Pre-heater max temperature, Pre-heater air reduction, Pre-heater Volume flow reduction, … |
| `filter` | feature | Enable Filter entities | 5 | e.g. EnableAirfilterAlarm, Z29 Airfilter SUP, Z30 Airfilter ETA, … |
| `fan_control` | feature | Enable Fan & flow entities | 1 | e.g. Fan regulation |
| `firmware` | feature | Enable Firmware / model entities | 1 | e.g. Firmware Version Touch Display |

**Tiers:** *core* = `basic`, always shown · *tier* = `advanced`, broad opt-in · *feature* = one subsystem, toggle independently · *expert* = untagged, only via **Enable all entities**.

> Groups are OR-combined: an entity is shown when *any* of its groups is enabled. Hidden entities also drop out of the Modbus read plan (a shown template keeps its own source registers polled).
