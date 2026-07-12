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

**Registers in this file:** 134 (Holding 54, Input 51, Coil 2, Discrete 27) · plus 2 composite template entities

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
| `0x13B3` (5043) — Solltemp. dyn. Kühlung<br>`solltemp_dyn_kuehlung` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13DA` (5082) — Auswahl Heizkreis 2<br>`auswahl_heizkreis_2` | Holding (4x) | FC03 read | uint16 |
| `0x13DC` (5084) — Heizkurvenendpunkt<br>`heizkurvenendpunkt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13DD` (5085) — Festwertemperatur<br>`festwertemperatur` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13DE` (5086) — Parallelverschiebung<br>`parallelverschiebung` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13DF` (5087) — Mischerlaufzeit<br>`mischerlaufzeit` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x005D` (93) — Mischerhysterese<br>`mischerhysterese` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x13E0` (5088) — Maximale Temperatur<br>`maximale_temperatur` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13E1` (5089) — Kühlung Raumsolltemperatur<br>`kuehlung_raumsolltemperatur` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x1398` (5016) — Anzahl Partystunden<br>`anzahl_partystunden` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x1399` (5017) — Anzahl Urlaubstage<br>`anzahl_urlaubstage` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13AA` (5034) — Stufen<br>`stufen` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x007F` (127) — Zeitwert Stoßlüften<br>`zeitwert_stosslueften` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13B9` (5049) — Hysterese<br>`hysterese` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13BB` (5051) — Solltemperatur<br>`solltemperatur` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0030` (48) — Mischerhysterese<br>`mischer_hysterese` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x139C` (5020) — Grenztemperatur parallel<br>`grenztemperatur_parallel` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x139D` (5021) — Mischerlaufzeit<br>`mischerlaufzeit_2` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13C9` (5065) — Absenkung<br>`absenkung` | Holding (4x) | FC03 read | uint16 |
| `0x13CA` (5066) — Start Stunde 1<br>`start_stunde_1` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13CB` (5067) — Start Minute 1<br>`start_minute_1` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13CC` (5068) — Ende Stunde 1<br>`ende_stunde_1` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13CD` (5069) — Ende Minute 1<br>`ende_minute_1` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13CE` (5070) — Start Stunde 2<br>`start_stunde_2` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13CF` (5071) — Start Minute 2<br>`start_minute_2` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13D0` (5072) — Ende Stunde 2<br>`ende_stunde_2` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13D1` (5073) — Ende Minute 2<br>`ende_minute_2` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13D2` (5074) — Sonntag<br>`sonntag` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13D3` (5075) — Montag<br>`montag` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13D4` (5076) — Dienstag<br>`dienstag` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13D5` (5077) — Mittwoch<br>`mittwoch` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13D6` (5078) — Donnerstag<br>`donnerstag` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13D7` (5079) — Freitag<br>`freitag` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13D8` (5080) — Samstag<br>`samstag` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x13D9` (5081) — Absenk- / Anhebwert<br>`absenk_anhebwert` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x138E` (5006) — Stunde<br>`stunde` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x138F` (5007) — Minute<br>`minute` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x1390` (5008) — Monat<br>`monat` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x1391` (5009) — Wochentag<br>`wochentag` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x1392` (5010) — Tag<br>`tag` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x1393` (5011) — Jahr<br>`jahr` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x142F` (5167) — Smart Grid<br>`smart_grid` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x138E` (5006) — Sync clock<br>`sync_clock` | Holding (4x) | FC16 write-only | uint16 |
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
| `0x000B` (11) — Raumtemperatur 1 / RT-RTH Econ<br>`raumtemperatur_1_rt_rth_econ` | Input (3x) | FC04 read | float16 |
| `0x000C` (12) — Raumtemperatur 2<br>`raumtemperatur_2` | Input (3x) | FC04 read | float16 |
| `0x000D` (13) — Raumfeuchte 1 / RT-RTH Econ<br>`raumfeuchte_1_rt_rth_econ` | Input (3x) | FC04 read | float16 |
| `0x000E` (14) — Raumfeuchte 2<br>`raumfeuchte_2` | Input (3x) | FC04 read | float16 |
| `0x0013` (19) — Vorlauftemperatur (R11)<br>`vorlauftemperatur` | Input (3x) | FC04 read | float16 |
| `0x0014` (20) — Rücklauftemperatur (R4)<br>`ruecklauftemperatur` | Input (3x) | FC04 read | float16 |
| `0x0015` (21) — Rücklauftemp. gem. Primärkreis (R24)<br>`ruecklauftemp_gem_primaerkreis` | Input (3x) | FC04 read | float16 |
| `0x0017` (23) — Solarspeicher (R22)<br>`solarspeicher` | Input (3x) | FC04 read | float16 |
| `0x0078` (120) — Außenlufttemperatur<br>`aussenlufttemperatur` | Input (3x) | FC04 read | float16 |
| `0x0079` (121) — Zulufttemperatur<br>`zulufttemperatur` | Input (3x) | FC04 read | float16 |
| `0x007A` (122) — Ablufttemperatur<br>`ablufttemperatur` | Input (3x) | FC04 read | float16 |
| `0x007B` (123) — Fortlufttemperatur<br>`fortlufttemperatur` | Input (3x) | FC04 read | float16 |
| `0x007D` (125) — Drehzahl Zuluftventilator<br>`drehzahl_zuluftventilator` | Input (3x) | FC04 read | float16 |
| `0x007E` (126) — Drehzahl Abluftventilator<br>`drehzahl_abluftventilator` | Input (3x) | FC04 read | float16 |
| `0x0049` (73) — Verdichter 2<br>`verdichter_2` | Input (3x) | FC04 read | uint16 |
| `0x004B` (75) — 2.Wärmeerzeuger (E10)<br>`waermeerzeuger` | Input (3x) | FC04 read | uint16 |
| `0x004E` (78) — Flanschheizung (E9)<br>`flanschheizung` | Input (3x) | FC04 read | uint16 |
| `0x004F` (79) — Schwimmbadpumpe (M19)<br>`schwimmbadpumpe` | Input (3x) | FC04 read | uint16 |
| `0x13E9` (5097) — Wärmemenge * Heizen 5-8<br>`waermemenge_heizen_5_8` | Input (3x) | FC04 read | uint16 |
| `0x13EA` (5098) — Wärmemenge * Heizen 9-12<br>`waermemenge_heizen_9_12` | Input (3x) | FC04 read | uint16 |
| `0x13EC` (5100) — Wärmemenge * Warmwasser 5-8<br>`waermemenge_warmwasser_5_8` | Input (3x) | FC04 read | uint16 |
| `0x13ED` (5101) — Wärmemenge * Warmwasser 9-12<br>`waermemenge_warmwasser_9_12` | Input (3x) | FC04 read | uint16 |
| `0x13EE` (5102) — Wärmemenge * Schwimmbad 1-4<br>`waermemenge_schwimmbad_1_4` | Input (3x) | FC04 read | uint16 |
| `0x13EF` (5103) — Wärmemenge * Schwimmbad 5-8<br>`waermemenge_schwimmbad_5_8` | Input (3x) | FC04 read | uint16 |
| `0x13F0` (5104) — Wärmemenge * Schwimmbad 9-12<br>`waermemenge_schwimmbad_9_12` | Input (3x) | FC04 read | uint16 |
| `0x0003` (3) — Smart Grid 1<br>`smart_grid_1` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0004` (4) — Smart Grid 2<br>`smart_grid_2` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
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
| `0x007D` (125) — Aktiv Zeit 1<br>`aktiv_zeit_1` | Discrete (1x) | FC02 read | bool (bit) |
| `0x007E` (126) — Aktiv Zeit 2<br>`aktiv_zeit_2` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0004` (4) — Schwimmbadthermostat<br>`schwimmbadthermostat` | Discrete (1x) | FC02 read | bool (bit) |
| `0x002A` (42) — Verdichter 2<br>`verdichter_2_2` | Discrete (1x) | FC02 read | bool (bit) |
| `0x002C` (44) — 2.Wärmeerzeuger (E10)<br>`waermeerzeuger_2` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0030` (48) — Mischer (M21) ZU<br>`mischer` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0032` (50) — Flanschheizung (E9)<br>`flanschheizung_2` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0035` (53) — Mischer (M22) Zu<br>`mischer_2` | Discrete (1x) | FC02 read | bool (bit) |
