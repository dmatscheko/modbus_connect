# Anhui QDF70B Pressure Sensor — entity groups

**Device file:** `custom_components/modbus_connect/device_configs/anhui-qdf70b-pressure-sensor.yaml`

Entities are split into groups you can switch on/off on the integration's companion **Configuration** device. `basic` is always on and never gets a switch; every other group gets an *Enable … entities* toggle. The **Enable all entities** master switch reveals everything, including untagged (expert) registers.

**Default groups (fresh install):** `basic`

**Total register + template entities:** 3

| Group | Kind | Switch on Configuration device | Entities | Covers |
| --- | --- | --- | --- | --- |
| `basic` | core | (always on) | 1 | Everyday essentials — main controls, headline sensors and the composite climate/fan entities. Always shown. |
| `advanced` | tier | Enable Advanced entities | 2 | The full detail — deep settings, per-component diagnostics and secondary readings. |

**Kinds:** *core* = `basic`, always shown · *tier* = `standard` (on by default) and `advanced`, broad opt-in detail levels · *feature* = one functional group (subsystem), toggle independently · *expert* = untagged, only via **Enable all entities**.

> Groups are OR-combined: an entity is shown when *any* of its groups is enabled. Hidden entities also drop out of the Modbus read plan (a shown template keeps its own source registers polled).
