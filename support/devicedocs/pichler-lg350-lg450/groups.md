# Pichler Lüftungsgerät LG 350 - LG 450 — entity groups

**Device file:** `custom_components/modbus_connect/device_configs/pichler-lg350-lg450.yaml`

Entities are split into groups you can switch on/off on the integration's device page. `basic` is always on and never gets a switch; every other group gets an *Enable … entities* toggle. The **Enable all entities** master switch reveals everything, including untagged (expert) registers.

**Default groups (fresh install):** `basic`, `standard`

**Total register + template entities:** 187

| Group | Tier | Switch on device page | Entities | Covers |
| --- | --- | --- | --- | --- |
| `basic` | core | (always on) | 11 | Everyday essentials — main controls, headline sensors and the composite climate/fan entities. Always shown. |
| `standard` | tier | Enable Standard entities | 24 | The everyday set beyond the basics: common setpoints, secondary readings and totals. On by default. |
| `advanced` | tier | Enable Advanced entities | 152 | The full detail — deep settings, per-component diagnostics and secondary readings. |
| `ventilation` | feature | Enable Ventilation & airflow entities | 38 | e.g. Betriebsmodus Sommer/Winter, Lüftungsstufe, Luftstrom Lüftungsstufe 1, … |
| `fan_control` | feature | Enable Fans entities | 5 | e.g. Fan regulation, Ventilatoren, Außenluft- & Fortluftklappen, … |
| `temperatures` | feature | Enable Air temperatures entities | 20 | e.g. Temperaturregelungsart, Soll Zulufttemperatur, Soll Raumlufttemperatur, … |
| `heat_exchanger` | feature | Enable Heat exchanger / bypass entities | 5 | e.g. EWT Sommer Umschaltpunkt, EWT Winter Umschaltpunkt, Bypassklappe Stellung, … |
| `preheater` | feature | Enable Pre/post-heater entities | 10 | e.g. Vorheizregister Relais Schwellwert, Vorheizregister Zieltemperatur, Pre-heater max temperature, … |
| `heating_cooling` | feature | Enable Heating & cooling entities | 8 | e.g. Freigabe Heizen, Freigabe Kühlen, Heizmischer Steuersignal, … |
| `faults` | feature | Enable Faults & alerts entities | 32 | e.g. Bedieneinheit Fehlerausgabe, EnableAirfilterAlarm, Summenstörmeldung, … |
| `filter` | feature | Enable Filter entities | 7 | e.g. Tauschintervall Filter, Filter zurücksetzen, Filter später erinnern, … |
| `co2_control` | feature | Enable CO2 control entities | 15 | e.g. CO2 Regelung, CO2 Sollwert, EPB CO2, … |
| `humidity_control` | feature | Enable Humidity control entities | 14 | e.g. Feuchte Regelung, Luftfeuchte Sollwert, Feuchte Regelung LS3 maximale Zeit, … |
| `external_sensors` | feature | Enable External sensors entities | 6 | e.g. Lüftungsstufe 3 Nachlaufzeit (External Din2), EnableExtractSmoke 0=off 1=NO 2=NC, Enable Presence mode, … |
| `summer_night_cooling` | feature | Enable Summer-night cooling entities | 14 | e.g. Enable Summernight cooling, Summernight cooling enable T, Summernight cooling disable T, … |
| `modbus_config` | feature | Enable Modbus configuration entities | 5 | e.g. Modbus address, Modbus baudrate, Modbus parity, … |
| `firmware` | feature | Enable Firmware / model entities | 6 | e.g. Sommer/Winter Zeitumstellung, Firmware Version Touch Display, Touch Display Show Air Quality, … |
| `system` | feature | Enable System & maintenance entities | 2 | e.g. System Zurücksetzen, Automatische Umschaltung Sommer/Winter |

**Tiers:** *core* = `basic`, always shown · *tier* = `standard` (on by default) and `advanced`, broad opt-in detail levels · *feature* = one subsystem, toggle independently · *expert* = untagged, only via **Enable all entities**.

> Groups are OR-combined: an entity is shown when *any* of its groups is enabled. Hidden entities also drop out of the Modbus read plan (a shown template keeps its own source registers polled).
