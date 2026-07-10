# Dimplex Sole/Wasser-Wärmepumpe SI 11TU — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/Dimplex-SI-11TU.yaml`

## Primary source

- **Dimplex — NWPM Modbus TCP Datenpunktliste (Wärmepumpenmanager)** (Dimplex wiki page v27, 2024-10-21)
- Source: [https://dimplex.atlassian.net/wiki/spaces/DW/pages/2873393288/NWPM+Modbus+TCP](https://dimplex.atlassian.net/wiki/spaces/DW/pages/2873393288/NWPM+Modbus+TCP)
- Source type: official-manufacturer (Dimplex wiki)
- Register addresses vs device file: verified — settings/holding 5015 Betriebsmodus, 5036 Parallelverschiebung, 5045/5145 Warmwasser, 5096 Wärmemenge; operating-data input 1 Außentemperatur, 103 Statusmeldung
- Local copy: [`NWPM-Modbus-TCP-Datenpunktliste.html`](./NWPM-Modbus-TCP-Datenpunktliste.html) — 245 KB

> Requires the optional NWPM / NWPM-Touch Modbus-TCP extension. The datapoint list carries two address columns — ‘WPM-Software J/L/M’ (the newer 5xxx map this device file uses) and legacy ‘WPM-Software H’. Saved as HTML via the Confluence REST API because the wiki is a JavaScript app. The doc lists function codes FC01/03/05/06/15/16.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 56 (Holding 11, Input 26, Discrete 19) · plus 2 composite template entities

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x1397` (5015) — Betriebsmodus<br>`operating_mode` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 6 opts |
| `0x13AC` (5036) — Heizung Parallelverschiebung<br>`heating_parallel_shift` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 39 opts |
| `0x002E` (46) — Heizung Raumtemperatur<br>`heating_room_temperature` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13AD` (5037) — heating_fixed_target _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x13AE` (5038) — Heizung Heizkurvenendpunkt<br>`heating_curve_end_point` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x002F` (47) — Heizung Hysterese<br>`heating_hysteresis` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x140A` (5130) — Softwaresperre Extern<br>`external_block_software` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x13B5` (5045) — Warmwasser Hysterese<br>`hot_water_hysteresis` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13B7` (5047) — hot_water_fixed_target _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x1419` (5145) — Warmwasser Solltemperatur Minimal<br>`hot_water_min_fixed_target` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13B8` (5048) — Warmwasser Solltemperatur Maximal<br>`hot_water_max_fixed_target` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0008` (8) — TEST What is this<br>`test_temp_what_is_this` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0001` (1) — Außentemperatur (R1)<br>`outside_temp` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0002` (2) — Heizung Rücklauftemperatur (R2)<br>`heating_return_temp` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x001B` (27) — 1. Heizkreis Temperatur (R5)<br>`heating_1st_loop_temp` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0009` (9) — 2. Heizkreis Temperatur (R?)<br>`heating_2nd_loop_temp` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x000A` (10) — 3. Heizkreis Temperatur (R13)<br>`heating_3rd_loop_temp` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0035` (53) — Heizung Rücklaufsolltemperatur<br>`heating_return_target` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x001D` (29) — 1. Heizkreis Rücklaufsolltemperatur<br>`heating_1st_loop_return_target` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0036` (54) — 2. Heizkreis Rücklaufsolltemperatur<br>`heating_2nd_loop_return_target` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0037` (55) — 3. Heizkreis Rücklaufsolltemperatur<br>`heating_3rd_loop_return_target` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0003` (3) — Warmwasser Temperatur (R3)<br>`hot_water_temp` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x003A` (58) — Warmwasser Solltemperatur<br>`hot_water_target` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0005` (5) — Vorlauftemperatur (R9)<br>`flow_temp` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0006` (6) — Wärmequelleneintrittstemperatur (R24)<br>`source_input_temp` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0007` (7) — Wärmequellenaustrittstemperatur (R6)<br>`source_output_temp` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0048` (72) — Verdichter 1 Laufzeit<br>`compressor1_hours` | Input (3x) | FC04 read | uint16 |
| `0x004A` (74) — Primärpumpe / Ventilator (M11) Laufzeit<br>`primary_pump_hours` | Input (3x) | FC04 read | uint16 |
| `0x004C` (76) — Heizungspumpe (M13) Laufzeit<br>`heating_pump_hours` | Input (3x) | FC04 read | uint16 |
| `0x004D` (77) — Warmwasserpumpe (M18) Laufzeit<br>`hot_water_pump_hours` | Input (3x) | FC04 read | uint16 |
| `0x0047` (71) — Zusatzumwälzpumpe (M16) Laufzeit<br>`additional_pump_hours` | Input (3x) | FC04 read | uint16 |
| `0x13E8` (5096) — Wärmemenge Heizung<br>`heating_energy` | Input (3x) | FC04 read | uint16 · sum_scale [1, 10000, 100000000] |
| `0x13EB` (5099) — Wärmemenge Warmwasser<br>`hot_water_energy` | Input (3x) | FC04 read | uint16 · sum_scale [1, 10000, 100000000] |
| `0x0067` (103) — Statusmeldung<br>`operation_status` | Input (3x) | FC04 read | uint16 · enum · 10 opts |
| `0x0068` (104) — Sperrmeldung<br>`blocking_status` | Input (3x) | FC04 read | uint16 · enum · 27 opts |
| `0x0069` (105) — Störmeldung<br>`fault_status` | Input (3x) | FC04 read | uint16 · enum · 24 opts |
| `0x006A` (106) — Sensorfehler<br>`sensor_status` | Input (3x) | FC04 read | uint16 · enum · 28 opts |
| `0x0003` (3) — Warmwasserthermostat<br>`hot_water_thermostat` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0005` (5) — EVU-Sperre<br>`utility_block` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0006` (6) — Sperre Extern<br>`external_block` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0029` (41) — Verdichter 1 Modus<br>`compressor1` | Discrete (1x) | FC02 read | bool (bit) |
| `0x002B` (43) — Sole Primärpumpe (M11) / Ventilator (M2) Modus<br>`primary_pump` | Discrete (1x) | FC02 read | bool (bit) |
| `0x002D` (45) — Heizungspumpe (M13) Modus<br>`heating_pump` | Discrete (1x) | FC02 read | bool (bit) |
| `0x002E` (46) — Warmwasserpumpe (M18) Modus<br>`hot_water_pump` | Discrete (1x) | FC02 read | bool (bit) |
| `0x002F` (47) — Mischer (M21) Modus<br>`mixer_open` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0031` (49) — Zusatzumwälzpumpe (M16) Modus<br>`additional_pump` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0033` (51) — Heizungspumpe (M15) Modus<br>`heating_pump_m15` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0034` (52) — Mischer (M22) Modus<br>`mixer_m22_open` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0038` (56) — Schwimmbadpumpe (M19) Modus<br>`pool_pump` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0039` (57) — Sammelstörmeldung (H5) Modus<br>`error_indicator` | Discrete (1x) | FC02 read | bool (bit) |
| `0x003B` (59) — Heizungspumpe (M14) Modus<br>`heating_pump_m14` | Discrete (1x) | FC02 read | bool (bit) |
| `0x003C` (60) — Kühlpumpe (M17) Modus<br>`cooling_pump` | Discrete (1x) | FC02 read | bool (bit) |
| `0x003D` (61) — Heizungspumpe (M20) Modus<br>`heating_pump_m20` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0042` (66) — Umschaltung Raumthermostate Heizen/Kühlen (N9) Modus<br>`room_thermostat_mode` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0044` (68) — Primärpumpe Kühlen (M12) Modus<br>`cooling_primary_pump` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0047` (71) — Solarpumpe (M23) Modus<br>`solar_pump` | Discrete (1x) | FC02 read | bool (bit) |
