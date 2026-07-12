# Pichler Lüftungsgerät LG 150 - LG 250 — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/pichler-lg150-lg250.yaml`

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

**Registers in this file:** 192 (Holding 101, Input 91) · plus 2 composite template entities

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
| `0x0003` (3) — Geothermal heat exchanger switching point summer<br>`ewt_sommer` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0004` (4) — Geothermal heat exchanger switching point winter<br>`ewt_winter` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0005` (5) — Bypass switching point<br>`bypass_schaltpunkt` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0006` (6) — Configuration<br>`konfiguration` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x0008` (8) — Post-heater<br>`nachheizregister` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x000D` (13) — Air volume flow difference, ETA-Balance<br>`luftdifferenz` | Holding (4x) | FC03 read · FC06 write | uint16 · -50 |
| `0x000E` (14) — Defrost_On<br>`abtau_ein` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x000F` (15) — Defrost time<br>`abluft_abtau_zeit` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0010` (16) — Defrost pause<br>`abtau_pause` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0011` (17) — Defrost difference<br>`abtau_differenz` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x0012` (18) — Supply fan stopping time<br>`zuluftstop_timer` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0013` (19) — Defrost_Speed limit exhaust fan<br>`drehzahl_grenze` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0014` (20) — Maximum supply air temperature<br>`zuluft_max_temperatur` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0015` (21) — Minimum supply air temperature<br>`zuluft_min_temperatur` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0019` (25) — KP_Heating<br>`kp_heizen` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x001A` (26) — TI_Heating<br>`ti_heizen` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x001B` (27) — Mixing valve cycle time<br>`mischertakt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x001C` (28) — Mixing valve running time<br>`mischerzeit` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x001D` (29) — Filter time<br>`filter_ladewert` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x001E` (30) — External digital input E2<br>`ext_e2_frost_stufe3` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x001F` (31) — External digital input E2 - Ventilation level 3 stopping time<br>`ext_luftstufe3_nachlauf` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0020` (32) — Condensate threshold<br>`kondensatwanne` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0022` (34) — Configuration ventilation level<br>`grundluftung_ein` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0023` (35) — Powersave at Standby<br>`powersave_at_stdby` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0024` (36) — Supply air setpoint cycle<br>`zuluft_sollwert_takt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0025` (37) — Internal post heater<br>`internes_nhr` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0026` (38) — Fresh air temperature<br>`internes_nhr_frischluft_temp` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0029` (41) — CO2 KP<br>`co2_reg_kp` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x002A` (42) — CO2 TI<br>`co2_reg_ti` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x002B` (43) — CO2 cycle<br>`co2_reg_takt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x002E` (46) — Relative humidity maximum time in level 3<br>`hum_reg_max_zeit` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x002F` (47) — Sensor configuration<br>`sensor_konfig` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x0030` (48) — Summer/Winter Time change<br>`uhr_sommer_winter_auto` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0031` (49) — Test Bypass damper<br>`test_var1` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 5 opts |
| `0x0032` (50) — Test supply air fan<br>`test_var2` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0033` (51) — Test exhaust air fan<br>`test_var3` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0034` (52) — Test mode<br>`test_var4` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x0035` (53) — Reset to factory settings<br>`reset_to_default` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0036` (54) — Reset operating hours counter<br>`reset_hour_counter` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x003F` (63) — Clear error log<br>`clear_error_log_button` | Holding (4x) | FC06 write-only | uint16 |
| `0x003F` (63) — Reset Filter Error<br>`reset_filter_error_button` | Holding (4x) | FC06 write-only | uint16 |
| `0x0037` (55) — Test SD-Card<br>`test_sd_card` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0038` (56) — Low supply air temperature setpoint<br>`zuluftsollwert_abgesenkt` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0039` (57) — Low room air temperature setpoint<br>`raumsollwert_abgesenkt` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x003A` (58) — Low extract air temperature setpoint<br>`abluftsollwert_abgesenkt` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x003B` (59) — Fan type<br>`ventilator_model` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x003C` (60) — Maximum fanspeed difference ventilation level 1<br>`max_fanspeed_ls1` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x003D` (61) — Maximum fanspeed difference ventilation level 2<br>`max_fanspeed_ls2` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x003E` (62) — Maximum fanspeed difference ventilation level 3<br>`max_fanspeed_ls3` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0040` (64) — AHU Type<br>`ahu_type` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x0040` (64) — ahu_type_hw _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 3 opts |
| `0x0041` (65) — Preheater control temperature<br>`vhr_ssr_temp` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0042` (66) — Pre heater SSR Reg KP<br>`vhr_ssr_pid_p` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0043` (67) — Pre heater SSR Reg TI<br>`vhr_ssr_pid_i` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0044` (68) — Pre heater SSR PWM Time<br>`vhr_ssr_pid_reg_takt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0045` (69) — Bypass damper type<br>`bypass_model` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0047` (71) — Counter bypass position<br>`bypass_counter_bypass` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0048` (72) — Counter heat recovery position<br>`bypass_counter_wrg` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0049` (73) — Damper counter preheater<br>`bypass_counter_vhr` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x004A` (74) — Damper M1 time<br>`bypass_m1_time` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x004B` (75) — Damper M2 time<br>`bypass_m2_time` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x004F` (79) — Modbus address<br>`modbusadresse` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0050` (80) — Modbus baud rate<br>`modbusbaudrate` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0051` (81) — Modbus parity<br>`modbusparitet` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x0052` (82) — Modbus write<br>`modbusschreibenerlaubt` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0063` (99) — Bypass current limit<br>`bypass_curent_lim` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0067` (103) — Time program air volume flow<br>`zeitprogrammluftenable` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0068` (104) — Time program temperature control<br>`zeitprogrammraumenable` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0069` (105) — Firmware Version Touch Display<br>`firmwareverbt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x006A` (106) — AdcNtcsBT<br>`adcntcsbt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x006B` (107) — AdcNtcPCBNtcIntBT<br>`adcntcpcbntcintbt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x006C` (108) — AdcNtcPCBNtcExtBT<br>`adcntcpcbntcextbt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x006D` (109) — CurrentModeBt<br>`currentmodebt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x006E` (110) — T2addAtLowPower<br>`t2addatlowpower` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x006F` (111) — T2addAtHiPower<br>`t2addathipower` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0070` (112) — T2-Offset<br>`t2offset` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0071` (113) — T2 internal to external compensation<br>`t2intextcomp` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x0072` (114) — Language<br>`language` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 10 opts |
| `0x0073` (115) — Screensaver time<br>`screensavertime` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0074` (116) — Lock main screen<br>`lockmainscreen` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0075` (117) — Back to home screen timeout<br>`tohomescreentimeout` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0076` (118) — Password<br>`password` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0077` (119) — User password<br>`userpassword` | Holding (4x) | FC03 read · FC06 write | uint16 |
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
| `0x0000` (0) — PIC_AD_T2<br>`pic_ad_t2` | Input (3x) | FC04 read | uint16 |
| `0x0001` (1) — PIC_AD_T1<br>`pic_ad_t1` | Input (3x) | FC04 read | uint16 |
| `0x0002` (2) — PIC_AD_0_10Vin_S1<br>`pic_ad_0_10vin_s1` | Input (3x) | FC04 read | uint16 |
| `0x0003` (3) — PIC_AD_0_10Vin_S2<br>`pic_ad_0_10vin_s2` | Input (3x) | FC04 read | uint16 |
| `0x0004` (4) — PIC_AD_24V<br>`pic_ad_24v` | Input (3x) | FC04 read | uint16 |
| `0x0005` (5) — PIC_AD_3V3<br>`pic_ad_3v3` | Input (3x) | FC04 read | uint16 |
| `0x0006` (6) — PIC_AD_T3<br>`pic_ad_t3` | Input (3x) | FC04 read | uint16 |
| `0x0007` (7) — PIC_AD_T4<br>`pic_ad_t4` | Input (3x) | FC04 read | uint16 |
| `0x0008` (8) — PIC_AD_T5<br>`pic_ad_t5` | Input (3x) | FC04 read | uint16 |
| `0x0009` (9) — PIC_AD_M1and2<br>`pic_ad_m1and2` | Input (3x) | FC04 read | uint16 |
| `0x000A` (10) — PIC_AD_Kondens<br>`pic_ad_kondens` | Input (3x) | FC04 read | uint16 |
| `0x000B` (11) — PIC_AD_Pressure_2<br>`pic_ad_pressure_2` | Input (3x) | FC04 read | uint16 |
| `0x000C` (12) — PIC_AD_Pressure_1<br>`pic_ad_pressure_1` | Input (3x) | FC04 read | uint16 |
| `0x000D` (13) — PIC_AD_Pressure_ref<br>`pic_ad_pressure_ref` | Input (3x) | FC04 read | uint16 |
| `0x000E` (14) — PIC_DIGin_E1<br>`pic_digin_e1` | Input (3x) | FC04 read | uint16 |
| `0x000F` (15) — PIC_DIGin_E2<br>`pic_digin_e2` | Input (3x) | FC04 read | uint16 |
| `0x0010` (16) — Relay K1 Preheater, GHX, ODA damper<br>`pic_relay_k1` | Input (3x) | FC04 read | uint16 |
| `0x0011` (17) — Relay K2 Fans<br>`pic_relay_k2` | Input (3x) | FC04 read | uint16 |
| `0x0012` (18) — Relay K3 Water post-heater pump<br>`pic_relay_k3` | Input (3x) | FC04 read | uint16 |
| `0x0013` (19) — Relay K4 Mixing valve opening/Post-heater level 1<br>`pic_relay_k4` | Input (3x) | FC04 read | uint16 |
| `0x0014` (20) — Relay K4 Mixing valve closing/Post-heater level 2<br>`pic_relay_k5` | Input (3x) | FC04 read | uint16 |
| `0x0015` (21) — Relay K6 Error indication (LG150)/Bypass damper<br>`pic_relay_k6` | Input (3x) | FC04 read | uint16 |
| `0x0016` (22) — SD card present<br>`pic_sd_card_present` | Input (3x) | FC04 read | uint16 |
| `0x0017` (23) — FW Version controller<br>`pic_lg150_sw_ver` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0018` (24) — FW version operating panel<br>`pic_mini_panel_sw_ver` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0019` (25) — LG model<br>`pic_lg_model` | Input (3x) | FC04 read | uint16 |
| `0x001A` (26) — PIC_Ventilator_model<br>`pic_ventilator_model` | Input (3x) | FC04 read | uint16 |
| `0x0023` (35) — S1 0-10Vin<br>`s1_0_10vin` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0024` (36) — S2 0-10Vin<br>`s2_0_10vin` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0025` (37) — E1 Din ext. Off<br>`e1_dig_in` | Input (3x) | FC04 read | uint16 |
| `0x0026` (38) — E2 Din ext. Level3<br>`e2_dig_in` | Input (3x) | FC04 read | uint16 |
| `0x0029` (41) — Condensate watchdog<br>`e3_in` | Input (3x) | FC04 read | uint16 |
| `0x002A` (42) — Pressure_P1<br>`pressure_p1` | Input (3x) | FC04 read | uint16 |
| `0x002B` (43) — Pressure_P2<br>`pressure_p2` | Input (3x) | FC04 read | uint16 |
| `0x0031` (49) — Current defrost time<br>`abtau_zeit` | Input (3x) | FC04 read | uint16 |
| `0x0034` (52) — Frost ExtractAir defrost status<br>`frost_abluft_abtau_status` | Input (3x) | FC04 read | uint16 |
| `0x0035` (53) — Frost ExtractAir defrost error counter<br>`frost_abluft_abtau_fehler_counter` | Input (3x) | FC04 read | uint16 |
| `0x0036` (54) — Mixing valve position<br>`mischer_pos` | Input (3x) | FC04 read | uint16 |
| `0x0037` (55) — SUP-T setpoint calculated<br>`zuluft_sollwert_berechnet` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0038` (56) — CO2 control signal<br>`co2_reg_out` | Input (3x) | FC04 read | uint16 |
| `0x0039` (57) — Summer/winter time<br>`uhr_summer_winter_status` | Input (3x) | FC04 read | uint16 |
| `0x003A` (58) — Preheater control signal<br>`vhr_ssr_reg_out` | Input (3x) | FC04 read | uint16 |
| `0x003C` (60) — Z01 T difference GHX<br>`status_fehler_z01` | Input (3x) | FC04 read | uint16 |
| `0x003D` (61) — Z02 Operating panel<br>`status_fehler_z02` | Input (3x) | FC04 read | uint16 |
| `0x003E` (62) — Z03 Frost protection Din2<br>`status_fehler_z03` | Input (3x) | FC04 read | uint16 |
| `0x003F` (63) — Z04 Exhaust fan shorted<br>`status_fehler_z04` | Input (3x) | FC04 read | uint16 |
| `0x0040` (64) — Z05 Supply fan shorted<br>`status_fehler_z05` | Input (3x) | FC04 read | uint16 |
| `0x0041` (65) — Z06 T1 Outdoor air shorted<br>`status_fehler_z06` | Input (3x) | FC04 read | uint16 |
| `0x0042` (66) — Z07 T2 Exhaust air shorted<br>`status_fehler_z07` | Input (3x) | FC04 read | uint16 |
| `0x0043` (67) — Z08 T3 Extract air shorted<br>`status_fehler_z08` | Input (3x) | FC04 read | uint16 |
| `0x0044` (68) — Z09 T4 Supply air shorted<br>`status_fehler_z09` | Input (3x) | FC04 read | uint16 |
| `0x0045` (69) — Z10 T5 ODA external shorted<br>`status_fehler_z10` | Input (3x) | FC04 read | uint16 |
| `0x0046` (70) — Z11 T1 Outdoor air open circuit<br>`status_fehler_z11` | Input (3x) | FC04 read | uint16 |
| `0x0047` (71) — Z12 T2 Exhaust air open circuit<br>`status_fehler_z12` | Input (3x) | FC04 read | uint16 |
| `0x0048` (72) — Z13 T3 Extract air open circuit<br>`status_fehler_z13` | Input (3x) | FC04 read | uint16 |
| `0x0049` (73) — Z14 T4 Supply air open circuit<br>`status_fehler_z14` | Input (3x) | FC04 read | uint16 |
| `0x004A` (74) — Z15 T5 ODA(LG250A)_SUP(Post-heater) external open circuit<br>`status_fehler_z15` | Input (3x) | FC04 read | uint16 |
| `0x004B` (75) — Z16 Change filters<br>`status_fehler_z16` | Input (3x) | FC04 read | uint16 |
| `0x004C` (76) — Z17 Condensate drip tray<br>`status_fehler_z17` | Input (3x) | FC04 read | uint16 |
| `0x004D` (77) — Z18 Dampers<br>`status_fehler_z18` | Input (3x) | FC04 read | uint16 |
| `0x004E` (78) — Z19 Fan speed difference - basic ventilation<br>`status_fehler_z19` | Input (3x) | FC04 read | uint16 |
| `0x004F` (79) — Z20 Fan speed difference too high<br>`status_fehler_z20` | Input (3x) | FC04 read | uint16 |
| `0x0050` (80) — Z21 Post-heater frost protection<br>`status_fehler_z21` | Input (3x) | FC04 read | uint16 |
| `0x0054` (84) — Total operating hours<br>`lufter_total_stunde` | Input (3x) | FC04 read | uint16 |
| `0x0056` (86) — Operating hours bypass<br>`bypass_klappe_stunde` | Input (3x) | FC04 read | uint16 |
| `0x0058` (88) — Operating hours ventilation level 1<br>`lufter1_stunde` | Input (3x) | FC04 read | uint16 |
