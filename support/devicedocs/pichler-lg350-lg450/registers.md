# Pichler Lüftungsgerät LG 350 - LG 450 — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/pichler-lg350-lg450.yaml`

## Primary source

- **Pichler / LS-Control — Modbus register list (controller ES2020, LG350/450/740/1000)** (v2.0.0)
- Source: [https://www.pichlerluft.at/unterlagen.html?file=files/content/downloads/LOGIN/LG%20350_LG%20450_LG%20740_LG%201000%20SK/LIST_Modbus_ES2020_FW_LG350_LG450_LG740_LG1000_v2.0.0.xlsx](https://www.pichlerluft.at/unterlagen.html?file=files/content/downloads/LOGIN/LG%20350_LG%20450_LG%20740_LG%201000%20SK/LIST_Modbus_ES2020_FW_LG350_LG450_LG740_LG1000_v2.0.0.xlsx)
- Source type: official-manufacturer (pichlerluft.at)
- Register addresses vs device file: verified — Setpoints = holding (FC03/FC06, base 1), Datapoints = input (FC04); device-file addresses & enums match (e.g. addr 7 Regelung 1=Abluft)
- Local copy: [`LIST_Modbus_ES2020_FW_LG350_LG450_LG740_LG1000_v2.0.0.xlsx`](./LIST_Modbus_ES2020_FW_LG350_LG450_LG740_LG1000_v2.0.0.xlsx) — 32 KB

> Same LS-Control workbook family (controller ES2020; also covers LG740 / LG1000). Holding = FC03 read / FC06 write; XLS address column is 1-based.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 186 (Holding 76, Input 110) · plus 2 composite template entities

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x0001` (1) — Betriebsmodus Sommer/Winter<br>`summer_winter_mode_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0002` (2) — Lüftungsstufe<br>`ventilation_level_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 5 opts |
| `0x0002` (2) — ventilation_level_raw _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0003` (3) — EWT Sommer Umschaltpunkt<br>`ghx_setpoint_summer` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0004` (4) — EWT Winter Umschaltpunkt<br>`ghx_setpoint_winter` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0007` (7) — Temperaturregelungsart<br>`temperature_control_mode_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x0009` (9) — Luftstrom Lüftungsstufe 1<br>`airflow_level_1` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x000A` (10) — Luftstrom Lüftungsstufe 2<br>`airflow_level_2` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x000B` (11) — Luftstrom Lüftungsstufe 3<br>`airflow_level_3` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x000C` (12) — Luftstrom Grundlüftung<br>`airflow_basic` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x000D` (13) — Vorheizregister Relais Schwellwert<br>`preheater_relay_threshold` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0016` (22) — Soll Zulufttemperatur<br>`supply_temp_setpoint` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0017` (23) — Soll Raumlufttemperatur<br>`room_temp_setpoint` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0018` (24) — Soll Ablufttemperatur<br>`extract_temp_setpoint` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x001F` (31) — Lüftungsstufe 3 Nachlaufzeit (External Din2)<br>`ext_e2_level_3_stop_time` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x001D` (29) — Tauschintervall Filter<br>`filter_tauschintervall_stunden_number` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0020` (32) — Raumtemperaturfühler Quelle<br>`room_temp_sensor_source` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0021` (33) — Filter zurücksetzen<br>`filter_reset_button` | Holding (4x) | FC06 write-only | uint16 |
| `0x0021` (33) — Filter später erinnern<br>`filter_snooze_button` | Holding (4x) | FC06 write-only | uint16 |
| `0x0022` (34) — Konfiguration Lüftungsstufe<br>`ventilation_level_config` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0023` (35) — Bedieneinheit Fehlerausgabe<br>`panel_error_output` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0027` (39) — CO2 Regelung<br>`co2_control_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0028` (40) — CO2 Sollwert<br>`co2_setpoint` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x002C` (44) — Feuchte Regelung<br>`humidity_control_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x002D` (45) — Luftfeuchte Sollwert<br>`humidity_setpoint` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x002E` (46) — Feuchte Regelung LS3 maximale Zeit<br>`humidity_level_3_max_time` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0030` (48) — Sommer/Winter Zeitumstellung<br>`dst_mode` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0031` (49) — Bypassklappe Stellung<br>`bypass_damper_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x0038` (56) — Soll Zulufttemperatur (Abgesenkt)<br>`supply_temp_setpoint_low` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0039` (57) — Soll Raumlufttemperatur (Abgesenkt)<br>`room_temp_setpoint_low` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x003A` (58) — Soll Ablufttemperatur (Abgesenkt)<br>`extract_temp_setpoint_low` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x003F` (63) — System Zurücksetzen<br>`system_reset_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x0041` (65) — Vorheizregister Zieltemperatur<br>`preheater_target` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0045` (69) — Automatische Umschaltung Sommer/Winter<br>`auto_summer_winter_switch` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0046` (70) — Lüftungsstufe 3 Maximale Zeit<br>`level_3_max_time` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x005F` (95) — Kanaldruck Zuluft Stufe 1<br>`supply_duct_pressure_1` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0060` (96) — Kanaldruck Zuluft Stufe 2<br>`supply_duct_pressure_2` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0061` (97) — Kanaldruck Zuluft Stufe 3<br>`supply_duct_pressure_3` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0062` (98) — Kanaldruck Zuluft Grundlüftung<br>`supply_duct_pressure_basic` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0063` (99) — Kanaldruck Abluft Stufe 1<br>`extract_duct_pressure_1` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0064` (100) — Kanaldruck Abluft Stufe 2<br>`extract_duct_pressure_2` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0065` (101) — Kanaldruck Abluft Stufe 3<br>`extract_duct_pressure_3` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0066` (102) — Kanaldruck Abluft Grundlüftung<br>`extract_duct_pressure_basic` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0053` (83) — Abluft-Balance Lüftungsstufe 1<br>`extract_balance_1` | Holding (4x) | FC03 read · FC06 write | uint16 · -500 |
| `0x0054` (84) — Abluft-Balance Lüftungsstufe 2<br>`extract_balance_2` | Holding (4x) | FC03 read · FC06 write | uint16 · -500 |
| `0x0055` (85) — Abluft-Balance Lüftungsstufe 3<br>`extract_balance_3` | Holding (4x) | FC03 read · FC06 write | uint16 · -500 |
| `0x0056` (86) — Abluft-Balance Grundlüftung<br>`extract_balance_basic` | Holding (4x) | FC03 read · FC06 write | uint16 · -500 |
| `0x0059` (89) — Freigabe Heizen<br>`heating_enable` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x005A` (90) — Freigabe Kühlen<br>`cooling_enable` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0067` (103) — Zeitprogramm Lüftungsstufen<br>`time_program_ventilation` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0068` (104) — Zeitprogramm Temperaturregelung<br>`time_program_temp_control` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0069` (105) — Firmware Version Touch Display<br>`firmwareversion_touchdisplay` | Holding (4x) | FC03 read | uint16 |
| `0x00D0` (208) — Modbus address<br>`modbusadresse` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x00D1` (209) — Modbus baudrate<br>`modbusbaudrate` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x00D2` (210) — Modbus parity<br>`modbusparitaet` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x003B` (59) — Activate modbus sensors<br>`modbussensorsenabled` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0050` (80) — Fan regulation<br>`fagregtype` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0052` (82) — EPB CO2<br>`epb_activate` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x006C` (108) — EPB CO2 Regulation<br>`epb_co2control` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0087` (135) — Touch Display Show Air Quality<br>`displayshowairqulity` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0088` (136) — Baudrate Modbus sensors<br>`baudratesensorbus` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0093` (147) — Pre-heater max temperature<br>`preheater_max_temp` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x009D` (157) — EnableAirfilterAlarm<br>`enableairfilteralarm` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x009E` (158) — EnableExtractSmoke 0=off 1=NO 2=NC<br>`enableextractsmoke` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x089A` (2202) — Relative humidity setpoint Winter<br>`humidity_setpoint_winter` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x089B` (2203) — Enable Presence mode<br>`userenablepresence` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x089C` (2204) — Enable Summernight cooling<br>`summernightcool_enable` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x089D` (2205) — Summernight cooling enable T<br>`summernightcool_temp_on` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x089E` (2206) — Summernight cooling disable T<br>`summernightcool_temp_off` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x089F` (2207) — Summernight cooling release T<br>`summernightcool_activation` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x08A0` (2208) — Summernight cooling start hour<br>`summernightcool_starttime_hour` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x08A1` (2209) — Summernight cooling start minute<br>`summernightcool_starttime_min` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x08A2` (2210) — Summernight cooling stop hour<br>`summernightcool_stoptime_hour` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x08A3` (2211) — Summernight cooling stop minute<br>`summernightcool_stoptime_min` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x08A4` (2212) — Summernight cooling ventilation level<br>`summernightcool_fanlevel` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x08A5` (2213) — Summernight cooling release ventilation level<br>`summernightcool_enable_level` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0002` (2) — L5/Ai1 CO2 Sensor<br>`l5_ai1_co2_sensor` | Input (3x) | FC04 read | uint16 · ×0.4884 |
| `0x0003` (3) — L7/Ai2 rF Sensor<br>`l7_ai2_rf_sensor` | Input (3x) | FC04 read | uint16 · ×0.02442 |
| `0x000D` (13) — Außentemperatur gedämpft<br>`outdoor_temp_damped` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0067` (103) — L7/Ai4 Abluft externer Sensor<br>`extract_temp_external` | Input (3x) | FC04 read | uint16 · ×0.01221 |
| `0x0004` (4) — Zuluft Temperatur (extern)<br>`supply_temp_external` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0005` (5) — Außenluft Temperatur (extern)<br>`outdoor_temp_external` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0009` (9) — Raum Temperatur (extern)<br>`room_temp_external` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x000A` (10) — Raumtemperatur TouchDisplay<br>`t9_touch_display` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x000B` (11) — Heizmischer Steuersignal<br>`heating_mixer_signal` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x000C` (12) — Kühlmischer Steuersignal<br>`cooling_mixer_signal` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x001A` (26) — Kombiregister Mischer Steuersignal<br>`combi_mixer_signal` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0010` (16) — Vorheizregister Relais<br>`relay_h2_preheater` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0011` (17) — Heizanforderung<br>`relay_h3_heat_demand` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0012` (18) — Kühlanforderung<br>`relay_h5_cool_demand` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0013` (19) — Ventilatoren<br>`relay_h67_fans` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0014` (20) — Bypassklappe Status<br>`bypass_damper_status` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0015` (21) — Außenluft- & Fortluftklappen<br>`relay_h9_air_dampers` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x001B` (27) — Pumpe Nachheizregister<br>`relay_h10_heating_pump` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x001C` (28) — Pumpe Kühl-/Kombiregister<br>`relay_h11_cooling_pump` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x001D` (29) — Summenstörmeldung<br>`collective_fault` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0029` (41) — Filtermeldung<br>`relay_h12b_filter_signal` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x001E` (30) — Temperatur Außenluft<br>`outdoor_air_temp` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x001F` (31) — Temperatur Fortluft<br>`exhaust_air_temp` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0020` (32) — Temperatur Abluft<br>`extract_air_temp` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0021` (33) — Temperatur Zuluft<br>`supply_air_temp` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0022` (34) — Temperatur Vorheizregister<br>`preheater_temp` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0025` (37) — Extern Aus / BMZ<br>`e1_din_extern_aus_bmz` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0026` (38) — Extern Lüftungsstufe 3<br>`ext_din_level_3` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0027` (39) — Drehzahl Zuluft<br>`supply_fan_speed` | Input (3x) | FC04 read | uint16 |
| `0x0028` (40) — Drehzahl Abluft<br>`exhaust_fan_speed` | Input (3x) | FC04 read | uint16 |
| `0x002A` (42) — Sollwert Zuluftvolumenstrom<br>`supply_airflow_setpoint` | Input (3x) | FC04 read | uint16 |
| `0x002B` (43) — Sollwert Abluftvolumenstrom<br>`extract_airflow_setpoint` | Input (3x) | FC04 read | uint16 |
| `0x002C` (44) — CO2 Modbus Sensor 1<br>`msensor1_co2` | Input (3x) | FC04 read | uint16 |
| `0x002D` (45) — Luftfeuchte Modbus Sensor 1<br>`msensor1_rf` | Input (3x) | FC04 read | uint16 |
| `0x002E` (46) — Istwert Zuluftvolumenstrom<br>`supply_airflow_actual` | Input (3x) | FC04 read | uint16 |
| `0x002F` (47) — Istwert Abluftvolumenstrom<br>`extract_airflow_actual` | Input (3x) | FC04 read | uint16 |
| `0x0030` (48) — Betriebsstatus<br>`operating_status` | Input (3x) | FC04 read | uint16 · enum · 7 opts |
| `0x0032` (50) — Filter Reststandzeit<br>`filter_reststandzeit` | Input (3x) | FC04 read | uint16 |
| `0x0037` (55) — Berechnete Zuluftsolltemperatur<br>`supply_temp_setpoint_calculated` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0038` (56) — CO2 Regelsignal Sollwert<br>`co2_regelsignal` | Input (3x) | FC04 read | uint16 |
| `0x003A` (58) — Vorheizregister PWM<br>`preheater_pwm` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x003B` (59) — Aktuelle Lüftungsstufe<br>`current_ventilation_level` | Input (3x) | FC04 read | uint16 · enum · 7 opts |
| `0x003C` (60) — Fehler Erdwärmetauscher<br>`fault_ghx` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x003D` (61) — Fehler Bedieneinheit<br>`fault_panel` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x003E` (62) — Fehler Frostschutz NHR (Din3)<br>`fault_postheater_frost` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x003F` (63) — Fehler Fortluftventilator<br>`fault_exhaust_fan` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0040` (64) — Fehler Zuluftventilator<br>`fault_supply_fan` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0041` (65) — Fehler Temperatur T1 (Außenluft)<br>`fault_t1_outdoor` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0042` (66) — Fehler Temperatur T2 (Fortluft)<br>`fault_t2_exhaust` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0043` (67) — Fehler Temperatur T3 (Abluft)<br>`fault_t3_extract` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0044` (68) — Fehler Temperatur T4 (Zuluft)<br>`fault_t4_supply` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0045` (69) — Fehler Temperatur T5 (Vorheizregister)<br>`fault_t5_preheater` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0046` (70) — Fehler Temperatur T6 (Zuluft extern)<br>`fault_t6_supply_external` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0047` (71) — Fehler Temperatur T7 (Außenluft extern)<br>`fault_t7_outdoor_external` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0048` (72) — Fehler Temperatur T8 (Raum extern)<br>`fault_t8_room_external` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0049` (73) — Fehler Ventilatoren Kommunikation<br>`fault_fan_communication` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x004A` (74) — Fehler Niedrige Zulufttemperatur<br>`fault_low_supply_temp` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x004B` (75) — Fehler Filtermeldung<br>`fault_filter` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x004C` (76) — Fehler Niedrige Vorheizregister Temperatur<br>`fault_low_preheater_temp` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0050` (80) — Fehler NHR Frostschutz<br>`fault_postheater_frost_protection` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0058` (88) — Fehler Modbus Sensoren<br>`fault_modbus_sensors` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0059` (89) — CO2 Sensor 1<br>`co2_sensor_1` | Input (3x) | FC04 read | uint16 |
| `0x005A` (90) — CO2 Sensor 2<br>`co2_sensor_2` | Input (3x) | FC04 read | uint16 |
| `0x005B` (91) — Feuchtesensor 1<br>`humidity_sensor_1` | Input (3x) | FC04 read | uint16 |
| `0x005C` (92) — Feuchtesensor 2<br>`humidity_sensor_2` | Input (3x) | FC04 read | uint16 |
| `0x0061` (97) — CO2 Modbus Sensor 2<br>`msensor2_co2` | Input (3x) | FC04 read | uint16 |
| `0x0062` (98) — Luftfeuchte Modbus Sensor 2<br>`msensor2_rf` | Input (3x) | FC04 read | uint16 |
| `0x0017` (23) — Firmware Version<br>`firmware_version` | Input (3x) | FC04 read | uint16 |
| `0x0019` (25) — Lüftungsgerät Modell<br>`lg_modell` | Input (3x) | FC04 read | uint16 · enum · 3 opts |
| `0x0069` (105) — Firmware Version TouchDisplay<br>`firmware_version_touch_display` | Input (3x) | FC04 read | uint16 |
| `0x006C` (108) — Extern Frostschutz<br>`ext_din_frost_protection` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0076` (118) — Zeitprogramm Raumtemperatur Status<br>`room_setpoint_time_program_status` | Input (3x) | FC04 read | uint16 · on=1 |
| `0x0077` (119) — Zeitprogramm Lüftungsstufe<br>`ventilation_time_program_status` | Input (3x) | FC04 read | uint16 · enum · 6 opts |
| `0x0051` (81) — Betriebsstunden Stufe 2<br>`level_2_hours` | Input (3x) | FC04 read | uint16 |
| `0x0052` (82) — Betriebsstunden Stufe 3<br>`level_3_hours` | Input (3x) | FC04 read | uint16 |
| `0x0053` (83) — Betriebsstunden Grundlüftung<br>`basic_ventilation_hours` | Input (3x) | FC04 read | uint16 |
| `0x0054` (84) — Betriebsstunden Gesamt<br>`total_ventilation_hours` | Input (3x) | FC04 read | uint16 |
| `0x0055` (85) — Betriebsstunden Heizregister<br>`heater_hours` | Input (3x) | FC04 read | uint16 |
| `0x0056` (86) — Betriebsstunden Bypass<br>`bypass_hours` | Input (3x) | FC04 read | uint16 |
| `0x0057` (87) — Betriebsstunden Stufe 1<br>`level_1_hours` | Input (3x) | FC04 read | uint16 |
| `0x1450` (5200) — CO2 air quality modbus sensor 3<br>`msensor3_co2_id_104` | Input (3x) | FC04 read | uint16 |
| `0x1451` (5201) — Relative humidity modbus sensor 3<br>`msensor3_rf_id_104` | Input (3x) | FC04 read | uint16 |
| `0x1452` (5202) — CO2 air quality modbus sensor 4<br>`msensor4_co2_id_105` | Input (3x) | FC04 read | uint16 |
| `0x1453` (5203) — Relative humidity modbus sensor 4<br>`msensor4_rf_id_105` | Input (3x) | FC04 read | uint16 |
| `0x1454` (5204) — CO2 air quality modbus sensor 5<br>`msensor5_co2_id_106` | Input (3x) | FC04 read | uint16 |
| `0x1455` (5205) — Relative humidity modbus sensor 5<br>`msensor5_rf_id_106` | Input (3x) | FC04 read | uint16 |
| `0x1456` (5206) — CO2 air quality modbus sensor 6<br>`msensor6_co2_id_4` | Input (3x) | FC04 read | uint16 |
| `0x1457` (5207) — Relative humidity modbus sensor 6<br>`msensor6_rf_id_4` | Input (3x) | FC04 read | uint16 |
| `0x1458` (5208) — Extract air duct pressure<br>`extract_duct_pressure` | Input (3x) | FC04 read | uint16 |
| `0x145A` (5210) — Supply air duct pressure<br>`supply_duct_pressure` | Input (3x) | FC04 read | uint16 |
| `0x145C` (5212) — Current CO2 control value<br>`aktueller_co2_wert` | Input (3x) | FC04 read | uint16 |
| `0x145D` (5213) — Error modbus communication to external pressure sensor<br>`fault_z23_pressure_sensor_comm` | Input (3x) | FC04 read | uint16 |
| `0x145E` (5214) — Low supply air duct pressure<br>`fault_z24_low_supply_duct_pressure` | Input (3x) | FC04 read | uint16 |
| `0x145F` (5215) — High supply air duct pressure<br>`fault_z25_high_supply_duct_pressure` | Input (3x) | FC04 read | uint16 |
| `0x1460` (5216) — Low extract air duct pressure<br>`fault_z26_low_extract_duct_pressure` | Input (3x) | FC04 read | uint16 |
| `0x1461` (5217) — High extract air duct pressure<br>`fault_z27_high_extract_duct_pressure` | Input (3x) | FC04 read | uint16 |
| `0x1462` (5218) — Pre-heater air reduction<br>`preheater_air_reduction` | Input (3x) | FC04 read | uint16 |
| `0x1463` (5219) — Pre-heater Volume flow reduction<br>`preheater_airflow_reduction` | Input (3x) | FC04 read | uint16 |
| `0x146A` (5226) — Z28 danger condensation<br>`z28_danger_condensation` | Input (3x) | FC04 read | uint16 |
| `0x146B` (5227) — Z29 Airfilter SUP<br>`z29_airfilter_sup` | Input (3x) | FC04 read | uint16 |
| `0x146C` (5228) — Z30 Airfilter ETA<br>`z30_airfilter_eta` | Input (3x) | FC04 read | uint16 |
| `0x146D` (5229) — Z31 External Preheater alarm<br>`z31_external_preheater_alarm` | Input (3x) | FC04 read | uint16 |
| `0x146E` (5230) — Z32 Door contact<br>`z32_door_contact` | Input (3x) | FC04 read | uint16 |
| `0x146F` (5231) — Filterpressure SUP<br>`sensorfilterpress_sup` | Input (3x) | FC04 read | uint16 |
| `0x1470` (5232) — Filterpressure ETA<br>`sensorfilterpress_eta` | Input (3x) | FC04 read | uint16 |
| `0x1471` (5233) — Current rH value<br>`currentrhvalue` | Input (3x) | FC04 read | uint16 |
| `0x1480` (5248) — Sommernacht Kühlung Status<br>`summernightcooling_status` | Input (3x) | FC04 read | uint16 |
| `0x1481` (5249) — Sommernacht Kühlung Testzeit<br>`summernightcooling_time` | Input (3x) | FC04 read | uint16 |
| `0x1482` (5250) — Sommernacht Kühlung Wiederholungszeit<br>`summernightcooling_time_check` | Input (3x) | FC04 read | uint16 |
| `0x1483` (5251) — Din1 Extern Sommernacht Kühlung aktiviert<br>`din1_externalsummernightcoolingenabled` | Input (3x) | FC04 read | uint16 |
