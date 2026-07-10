# Pichler Lüftungsgerät LG 150 - LG 250 — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/Pichler-LG150-LG250.yaml`

## Primary source

- **Pichler / LS-Control — Modbus register list (controller ES1015, LG150AB/LG250A)** (v2.0.0)
- Source: [https://www.pichlerluft.at/unterlagen.html?file=files/content/downloads/LOGIN/LG%20150AB-LG250A/LIST_Modbus_ES1015_FW_LG150AB_LG250A_v2.0.0.xlsx](https://www.pichlerluft.at/unterlagen.html?file=files/content/downloads/LOGIN/LG%20150AB-LG250A/LIST_Modbus_ES1015_FW_LG150AB_LG250A_v2.0.0.xlsx)
- Source type: official-manufacturer (pichlerluft.at)
- Register addresses vs device file: verified — Setpoints sheet = holding (FC03 read / FC06 write, address base 1), Datapoints = input (FC04, base 0); device-file holding addresses & enums map 1:1
- Local copy: [`LIST_Modbus_ES1015_FW_LG150AB_LG250A_v2.0.0.xlsx`](./LIST_Modbus_ES1015_FW_LG150AB_LG250A_v2.0.0.xlsx) — 33 KB

> Pichler / LS-Control workbook (sheets: Modbus Settings / Setpoints / Datapoints); controller ES1015. The XLS ‘Address’ column is 1-based; the device file uses the same 1-based holding addresses.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 43 (Holding 18, Input 25) · plus 2 composite template entities

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x0001` (1) — Betriebsmodus Sommer/Winter<br>`betriebsmodus_sommer_winter_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0002` (2) — Lüftungsstufe<br>`luftungsstufe_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 5 opts |
| `0x0002` (2) — luftungsstufe_raw _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0007` (7) — Temperaturregelungsart<br>`temperaturregelungsart_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x002C` (44) — Luftfeuchtigkeit Regelung<br>`luftfeuchtigkeit_regelung_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0027` (39) — CO2 Regelung<br>`co2_regelung_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0021` (33) — Filter zurücksetzen<br>`filter_reset_button` | Holding (4x) | FC06 write-only | uint16 |
| `0x0021` (33) — Filter später erinnern<br>`filter_snooze_button` | Holding (4x) | FC06 write-only | uint16 |
| `0x0009` (9) — Luftstrom Lüftungsstufe 1<br>`volumenstrom_luftungsstufe_1_number` | Holding (4x) | FC03 read · FC06 write | uint16 · ×10 |
| `0x000A` (10) — Luftstrom Lüftungsstufe 2<br>`volumenstrom_luftungsstufe_2_number` | Holding (4x) | FC03 read · FC06 write | uint16 · ×10 |
| `0x000B` (11) — Luftstrom Lüftungsstufe 3<br>`volumenstrom_luftungsstufe_3_number` | Holding (4x) | FC03 read · FC06 write | uint16 · ×10 |
| `0x000C` (12) — Luftstrom Grundlüftung<br>`volumenstrom_grundluftung_number` | Holding (4x) | FC03 read · FC06 write | uint16 · ×10 |
| `0x0046` (70) — Lüftungsstufe 3 Timer<br>`timer_luftungsstufe_3_number` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0016` (22) — Soll Zulufttemperatur<br>`soll_zulufttemperatur_number` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0017` (23) — Soll Raumlufttemperatur<br>`soll_raumlufttemperatur_number` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0018` (24) — Soll Ablufttemperatur<br>`soll_ablufttemperatur_number` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x002D` (45) — Luftfeuchtigkeit Maximum<br>`luftfeuchtigkeit_maximum_number` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0028` (40) — CO2 Maximum<br>`co2_maximum_number` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x001D` (29) — Temperatur Raum Display<br>`temperatur_raum_display` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x001E` (30) — Temperatur Außenluft<br>`temperatur_aussenluft` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x001F` (31) — Temperatur Fortluft<br>`temperatur_fortluft` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0020` (32) — Abluft Temperatur<br>`temperatur_abluft` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0021` (33) — Zuluft Temperatur<br>`temperatur_zuluft` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0022` (34) — Temperatur Nachheizregister Zuluft<br>`temperatur_nachheizregister_zuluft` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0027` (39) — Zuluft Ventilatordrehzahl<br>`zuluftventilator_drehzahl` | Input (3x) | FC04 read | uint16 |
| `0x0028` (40) — Abluft Ventilatordrehzahl<br>`abluftventilator_drehzahl` | Input (3x) | FC04 read | uint16 |
| `0x002C` (44) — Zuluft Ventilatorleistung<br>`zuluftventilator` | Input (3x) | FC04 read | uint16 |
| `0x002D` (45) — Abluft Ventilatorleistung<br>`abluftventilator` | Input (3x) | FC04 read | uint16 |
| `0x002E` (46) — Zuluft Luftstrom<br>`zuluftvolumenstrom` | Input (3x) | FC04 read | uint16 |
| `0x002F` (47) — Abluft Luftstrom<br>`abluftvolumenstrom` | Input (3x) | FC04 read | uint16 |
| `0x0030` (48) — Betriebsstatus<br>`betriebsstatus` | Input (3x) | FC04 read | uint16 · enum · 7 opts |
| `0x0032` (50) — Filter Reststandzeit<br>`filter_reststandzeit` | Input (3x) | FC04 read | uint16 |
| `0x003B` (59) — Aktuelle Lüftungsstufe<br>`aktuelle_luftungsstufe` | Input (3x) | FC04 read | uint16 · enum · 7 opts |
| `0x0057` (87) — Lüfter 1 Stunden<br>`lufter_1_stunden` | Input (3x) | FC04 read | uint16 |
| `0x0051` (81) — Lüfter 2 Stunden<br>`lufter_2_stunden` | Input (3x) | FC04 read | uint16 |
| `0x0052` (82) — Lüfter 3 Stunden<br>`lufter_3_stunden` | Input (3x) | FC04 read | uint16 |
| `0x0053` (83) — Lüfter Grund Stunden<br>`lufter_grund_stunden` | Input (3x) | FC04 read | uint16 |
| `0x0055` (85) — Heizelement Stunden<br>`heizelement_stunden` | Input (3x) | FC04 read | uint16 |
| `0x0033` (51) — Position Bypassklappe<br>`position_bypassklappe` | Input (3x) | FC04 read | uint16 · enum · 4 opts |
| `0x005B` (91) — Feuchtesensor 1<br>`feuchtesensor_1` | Input (3x) | FC04 read | uint16 |
| `0x005C` (92) — Feuchtesensor 2<br>`feuchtesensor_2` | Input (3x) | FC04 read | uint16 |
| `0x0059` (89) — CO2 Sensor 1<br>`co2_sensor_1` | Input (3x) | FC04 read | uint16 |
| `0x005A` (90) — CO2 Sensor 2<br>`co2_sensor_2` | Input (3x) | FC04 read | uint16 |
