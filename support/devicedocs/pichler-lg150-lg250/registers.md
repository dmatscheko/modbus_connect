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
| `0x0001` (1) — Betriebsmodus Sommer/Winter<br>`summer_winter_mode_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0002` (2) — Lüftungsstufe<br>`ventilation_level_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 5 opts |
| `0x0002` (2) — ventilation_level_raw _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0007` (7) — Temperaturregelungsart<br>`temperature_control_mode_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x002C` (44) — Luftfeuchtigkeit Regelung<br>`humidity_control_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0027` (39) — CO2 Regelung<br>`co2_control_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0021` (33) — Filter zurücksetzen<br>`filter_reset_button` | Holding (4x) | FC06 write-only | uint16 |
| `0x0021` (33) — Filter später erinnern<br>`filter_snooze_button` | Holding (4x) | FC06 write-only | uint16 |
| `0x0009` (9) — Luftstrom Lüftungsstufe 1<br>`airflow_level_1` | Holding (4x) | FC03 read · FC06 write | uint16 · ×10 |
| `0x000A` (10) — Luftstrom Lüftungsstufe 2<br>`airflow_level_2` | Holding (4x) | FC03 read · FC06 write | uint16 · ×10 |
| `0x000B` (11) — Luftstrom Lüftungsstufe 3<br>`airflow_level_3` | Holding (4x) | FC03 read · FC06 write | uint16 · ×10 |
| `0x000C` (12) — Luftstrom Grundlüftung<br>`airflow_basic` | Holding (4x) | FC03 read · FC06 write | uint16 · ×10 |
| `0x0046` (70) — Lüftungsstufe 3 Timer<br>`level_3_timer` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0016` (22) — Soll Zulufttemperatur<br>`supply_temp_setpoint` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0017` (23) — Soll Raumlufttemperatur<br>`room_temp_setpoint` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0018` (24) — Soll Ablufttemperatur<br>`extract_temp_setpoint` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x002D` (45) — Luftfeuchtigkeit Maximum<br>`humidity_max` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0028` (40) — CO2 Maximum<br>`co2_max` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0003` (3) — Geothermal heat exchanger switching point summer<br>`ghx_setpoint_summer` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0004` (4) — Geothermal heat exchanger switching point winter<br>`ghx_setpoint_winter` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0005` (5) — Bypass switching point<br>`bypass_switch_point` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0006` (6) — Configuration<br>`configuration` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x0008` (8) — Post-heater<br>`post_heater` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x000D` (13) — Air volume flow difference, ETA-Balance<br>`airflow_difference` | Holding (4x) | FC03 read · FC06 write | uint16 · -50 |
| `0x000E` (14) — Defrost on<br>`defrost_on` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x000F` (15) — Defrost time<br>`defrost_time` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0010` (16) — Defrost pause<br>`defrost_pause` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0011` (17) — Defrost difference<br>`defrost_difference` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x0012` (18) — Supply fan stopping time<br>`supply_fan_stop_time` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0013` (19) — Defrost speed limit exhaust fan<br>`exhaust_fan_speed_limit` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0014` (20) — Maximum supply air temperature<br>`supply_temp_max` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0015` (21) — Minimum supply air temperature<br>`supply_temp_min` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0019` (25) — Heating KP<br>`heating_kp` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x001A` (26) — Heating TI<br>`heating_ti` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x001B` (27) — Mixing valve cycle time<br>`mischertakt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x001C` (28) — Mixing valve running time<br>`mixing_valve_time` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x001D` (29) — Filter time<br>`filter_time` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x001E` (30) — External digital input E2<br>`ext_e2_frost_level_3` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x001F` (31) — External digital input E2 - Ventilation level 3 stopping time<br>`ext_level_3_stop_time` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0020` (32) — Condensate threshold<br>`condensate_threshold` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0022` (34) — Configuration ventilation level<br>`basic_ventilation_config` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0023` (35) — Powersave at Standby<br>`powersave_at_stdby` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0024` (36) — Supply air setpoint cycle<br>`supply_setpoint_cycle` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0025` (37) — Internal post heater<br>`internes_nhr` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0026` (38) — Fresh air temperature<br>`fresh_air_temp` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0029` (41) — CO2 KP<br>`co2_reg_kp` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x002A` (42) — CO2 TI<br>`co2_reg_ti` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x002B` (43) — CO2 cycle<br>`co2_reg_takt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x002E` (46) — Relative humidity maximum time in level 3<br>`humidity_max_time_level_3` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x002F` (47) — Sensor configuration<br>`sensor_config` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x0030` (48) — Summer/Winter Time change<br>`dst_auto` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0031` (49) — Test Bypass damper<br>`test_var1` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 5 opts |
| `0x0032` (50) — Test supply air fan<br>`test_var2` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0033` (51) — Test exhaust air fan<br>`test_var3` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0034` (52) — Test mode<br>`test_var4` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x0035` (53) — Reset to factory settings<br>`reset_to_default` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0036` (54) — Reset operating hours counter<br>`reset_hour_counter` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x003F` (63) — Clear error log<br>`clear_error_log_button` | Holding (4x) | FC06 write-only | uint16 |
| `0x003F` (63) — Reset Filter Error<br>`reset_filter_error_button` | Holding (4x) | FC06 write-only | uint16 |
| `0x0037` (55) — Test SD-Card<br>`test_sd_card` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0038` (56) — Low supply air temperature setpoint<br>`supply_setpoint_low` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0039` (57) — Low room air temperature setpoint<br>`room_setpoint_low` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x003A` (58) — Low extract air temperature setpoint<br>`extract_setpoint_low` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x003B` (59) — Fan type<br>`fan_type` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x003C` (60) — Maximum fanspeed difference ventilation level 1<br>`max_fanspeed_ls1` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x003D` (61) — Maximum fanspeed difference ventilation level 2<br>`max_fanspeed_ls2` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x003E` (62) — Maximum fanspeed difference ventilation level 3<br>`max_fanspeed_ls3` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0040` (64) — AHU Type<br>`ahu_type` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x0040` (64) — ahu_type_hw _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 3 opts |
| `0x0041` (65) — Preheater control temperature<br>`vhr_ssr_temp` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 · -100 |
| `0x0042` (66) — Pre heater SSR Reg KP<br>`vhr_ssr_pid_p` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0043` (67) — Pre heater SSR Reg TI<br>`vhr_ssr_pid_i` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0044` (68) — Pre heater SSR PWM Time<br>`vhr_ssr_pid_reg_takt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0045` (69) — Bypass damper type<br>`bypass_damper_type` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0047` (71) — Counter bypass position<br>`bypass_position_counter` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0048` (72) — Counter heat recovery position<br>`heat_recovery_position_counter` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0049` (73) — Damper counter preheater<br>`preheater_damper_counter` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x004A` (74) — Damper M1 time<br>`damper_m1_time` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x004B` (75) — Damper M2 time<br>`damper_m2_time` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x004F` (79) — Modbus address<br>`modbusadresse` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0050` (80) — Modbus baud rate<br>`modbusbaudrate` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0051` (81) — Modbus parity<br>`modbusparitet` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x0052` (82) — Modbus write<br>`modbusschreibenerlaubt` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0063` (99) — Bypass current limit<br>`bypass_current_limit` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0067` (103) — Time program air volume flow<br>`time_program_airflow_enable` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0068` (104) — Time program temperature control<br>`time_program_temp_enable` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0069` (105) — Firmware Version Touch Display<br>`firmwareverbt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x006A` (106) — AdcNtcsBT<br>`adc_ntc_sbt` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x006B` (107) — AdcNtcPCBNtcIntBT<br>`adc_ntc_pcb_int` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x006C` (108) — AdcNtcPCBNtcExtBT<br>`adc_ntc_pcb_ext` | Holding (4x) | FC03 read · FC06 write | uint16 |
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
| `0x001D` (29) — Temperatur Raum Display<br>`room_temp_display` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x001E` (30) — Temperatur Außenluft<br>`outdoor_air_temp` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x001F` (31) — Temperatur Fortluft<br>`exhaust_air_temp` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0020` (32) — Abluft Temperatur<br>`extract_air_temp` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0021` (33) — Zuluft Temperatur<br>`supply_air_temp` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0022` (34) — Temperatur Nachheizregister Zuluft<br>`post_heater_supply_temp` | Input (3x) | FC04 read | uint16 · ×0.1 · -100 |
| `0x0027` (39) — Zuluft Ventilatordrehzahl<br>`supply_fan_speed` | Input (3x) | FC04 read | uint16 |
| `0x0028` (40) — Abluft Ventilatordrehzahl<br>`exhaust_fan_speed` | Input (3x) | FC04 read | uint16 |
| `0x002C` (44) — Zuluft Ventilatorleistung<br>`supply_fan_power` | Input (3x) | FC04 read | uint16 |
| `0x002D` (45) — Abluft Ventilatorleistung<br>`exhaust_fan_power` | Input (3x) | FC04 read | uint16 |
| `0x002E` (46) — Zuluft Luftstrom<br>`supply_airflow` | Input (3x) | FC04 read | uint16 |
| `0x002F` (47) — Abluft Luftstrom<br>`exhaust_airflow` | Input (3x) | FC04 read | uint16 |
| `0x0030` (48) — Betriebsstatus<br>`operating_status` | Input (3x) | FC04 read | uint16 · enum · 7 opts |
| `0x0032` (50) — Filter Reststandzeit<br>`filter_remaining_time` | Input (3x) | FC04 read | uint16 |
| `0x003B` (59) — Aktuelle Lüftungsstufe<br>`current_ventilation_level` | Input (3x) | FC04 read | uint16 · enum · 7 opts |
| `0x0057` (87) — Lüfter 1 Stunden<br>`fan_1_hours` | Input (3x) | FC04 read | uint16 |
| `0x0051` (81) — Lüfter 2 Stunden<br>`fan_2_hours` | Input (3x) | FC04 read | uint16 |
| `0x0052` (82) — Lüfter 3 Stunden<br>`fan_3_hours` | Input (3x) | FC04 read | uint16 |
| `0x0053` (83) — Lüfter Grund Stunden<br>`fan_basic_hours` | Input (3x) | FC04 read | uint16 |
| `0x0055` (85) — Heizelement Stunden<br>`heating_element_hours` | Input (3x) | FC04 read | uint16 |
| `0x0033` (51) — Position Bypassklappe<br>`bypass_damper_position` | Input (3x) | FC04 read | uint16 · enum · 4 opts |
| `0x005B` (91) — Feuchtesensor 1<br>`humidity_sensor_1` | Input (3x) | FC04 read | uint16 |
| `0x005C` (92) — Feuchtesensor 2<br>`humidity_sensor_2` | Input (3x) | FC04 read | uint16 |
| `0x0059` (89) — CO2 Sensor 1<br>`co2_sensor_1` | Input (3x) | FC04 read | uint16 |
| `0x005A` (90) — CO2 Sensor 2<br>`co2_sensor_2` | Input (3x) | FC04 read | uint16 |
| `0x0000` (0) — ADC temperature T2<br>`adc_temp_t2` | Input (3x) | FC04 read | uint16 |
| `0x0001` (1) — ADC temperature T1<br>`adc_temp_t1` | Input (3x) | FC04 read | uint16 |
| `0x0002` (2) — ADC analog input S1 (0-10 V)<br>`adc_analog_in_s1` | Input (3x) | FC04 read | uint16 |
| `0x0003` (3) — ADC analog input S2 (0-10 V)<br>`adc_analog_in_s2` | Input (3x) | FC04 read | uint16 |
| `0x0004` (4) — ADC 24 V rail<br>`adc_24v_rail` | Input (3x) | FC04 read | uint16 |
| `0x0005` (5) — ADC 3.3 V rail<br>`adc_3v3_rail` | Input (3x) | FC04 read | uint16 |
| `0x0006` (6) — ADC temperature T3<br>`adc_temp_t3` | Input (3x) | FC04 read | uint16 |
| `0x0007` (7) — ADC temperature T4<br>`adc_temp_t4` | Input (3x) | FC04 read | uint16 |
| `0x0008` (8) — ADC temperature T5<br>`adc_temp_t5` | Input (3x) | FC04 read | uint16 |
| `0x0009` (9) — ADC motors M1 & M2<br>`adc_motors_m1_m2` | Input (3x) | FC04 read | uint16 |
| `0x000A` (10) — ADC condensate sensor<br>`adc_condensate` | Input (3x) | FC04 read | uint16 |
| `0x000B` (11) — ADC pressure 2<br>`adc_pressure_2` | Input (3x) | FC04 read | uint16 |
| `0x000C` (12) — ADC pressure 1<br>`adc_pressure_1` | Input (3x) | FC04 read | uint16 |
| `0x000D` (13) — ADC pressure reference<br>`adc_pressure_ref` | Input (3x) | FC04 read | uint16 |
| `0x000E` (14) — Digital input E1<br>`digital_in_e1` | Input (3x) | FC04 read | uint16 |
| `0x000F` (15) — Digital input E2<br>`digital_in_e2` | Input (3x) | FC04 read | uint16 |
| `0x0010` (16) — Relay K1 Preheater, GHX, ODA damper<br>`relay_k1` | Input (3x) | FC04 read | uint16 |
| `0x0011` (17) — Relay K2 Fans<br>`relay_k2` | Input (3x) | FC04 read | uint16 |
| `0x0012` (18) — Relay K3 Water post-heater pump<br>`relay_k3` | Input (3x) | FC04 read | uint16 |
| `0x0013` (19) — Relay K4 Mixing valve opening/Post-heater level 1<br>`relay_k4` | Input (3x) | FC04 read | uint16 |
| `0x0014` (20) — Relay K4 Mixing valve closing/Post-heater level 2<br>`relay_k5` | Input (3x) | FC04 read | uint16 |
| `0x0015` (21) — Relay K6 Error indication (LG150)/Bypass damper<br>`relay_k6` | Input (3x) | FC04 read | uint16 |
| `0x0016` (22) — SD card present<br>`sd_card_present` | Input (3x) | FC04 read | uint16 |
| `0x0017` (23) — controller_fw_version _(internal)_ | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0018` (24) — panel_fw_version _(internal)_ | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0019` (25) — LG model<br>`lg_model` | Input (3x) | FC04 read | uint16 |
| `0x001A` (26) — Fan model<br>`fan_model` | Input (3x) | FC04 read | uint16 |
| `0x0023` (35) — S1 0-10Vin<br>`s1_0_10vin` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0024` (36) — S2 0-10Vin<br>`s2_0_10vin` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0025` (37) — E1 Din ext. Off<br>`e1_dig_in` | Input (3x) | FC04 read | uint16 |
| `0x0026` (38) — E2 Din ext. Level3<br>`e2_dig_in` | Input (3x) | FC04 read | uint16 |
| `0x0029` (41) — Condensate watchdog<br>`e3_in` | Input (3x) | FC04 read | uint16 |
| `0x002A` (42) — Pressure_P1<br>`pressure_p1` | Input (3x) | FC04 read | uint16 |
| `0x002B` (43) — Pressure_P2<br>`pressure_p2` | Input (3x) | FC04 read | uint16 |
| `0x0031` (49) — Current defrost time<br>`current_defrost_time` | Input (3x) | FC04 read | uint16 |
| `0x0034` (52) — Frost ExtractAir defrost status<br>`extract_defrost_status` | Input (3x) | FC04 read | uint16 |
| `0x0035` (53) — Frost ExtractAir defrost error counter<br>`extract_defrost_error_counter` | Input (3x) | FC04 read | uint16 |
| `0x0036` (54) — Mixing valve position<br>`mischer_pos` | Input (3x) | FC04 read | uint16 |
| `0x0037` (55) — SUP-T setpoint calculated<br>`supply_setpoint_calculated` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0038` (56) — CO2 control signal<br>`co2_reg_out` | Input (3x) | FC04 read | uint16 |
| `0x0039` (57) — Summer/winter time<br>`dst_status` | Input (3x) | FC04 read | uint16 |
| `0x003A` (58) — Preheater control signal<br>`vhr_ssr_reg_out` | Input (3x) | FC04 read | uint16 |
| `0x003C` (60) — Z01 T difference GHX<br>`fault_z01` | Input (3x) | FC04 read | uint16 |
| `0x003D` (61) — Z02 Operating panel<br>`fault_z02` | Input (3x) | FC04 read | uint16 |
| `0x003E` (62) — Z03 Frost protection Din2<br>`fault_z03` | Input (3x) | FC04 read | uint16 |
| `0x003F` (63) — Z04 Exhaust fan shorted<br>`fault_z04` | Input (3x) | FC04 read | uint16 |
| `0x0040` (64) — Z05 Supply fan shorted<br>`fault_z05` | Input (3x) | FC04 read | uint16 |
| `0x0041` (65) — Z06 T1 Outdoor air shorted<br>`fault_z06` | Input (3x) | FC04 read | uint16 |
| `0x0042` (66) — Z07 T2 Exhaust air shorted<br>`fault_z07` | Input (3x) | FC04 read | uint16 |
| `0x0043` (67) — Z08 T3 Extract air shorted<br>`fault_z08` | Input (3x) | FC04 read | uint16 |
| `0x0044` (68) — Z09 T4 Supply air shorted<br>`fault_z09` | Input (3x) | FC04 read | uint16 |
| `0x0045` (69) — Z10 T5 ODA external shorted<br>`fault_z10` | Input (3x) | FC04 read | uint16 |
| `0x0046` (70) — Z11 T1 Outdoor air open circuit<br>`fault_z11` | Input (3x) | FC04 read | uint16 |
| `0x0047` (71) — Z12 T2 Exhaust air open circuit<br>`fault_z12` | Input (3x) | FC04 read | uint16 |
| `0x0048` (72) — Z13 T3 Extract air open circuit<br>`fault_z13` | Input (3x) | FC04 read | uint16 |
| `0x0049` (73) — Z14 T4 Supply air open circuit<br>`fault_z14` | Input (3x) | FC04 read | uint16 |
| `0x004A` (74) — Z15 T5 ODA(LG250A)_SUP(Post-heater) external open circuit<br>`fault_z15` | Input (3x) | FC04 read | uint16 |
| `0x004B` (75) — Z16 Change filters<br>`fault_z16` | Input (3x) | FC04 read | uint16 |
| `0x004C` (76) — Z17 Condensate drip tray<br>`fault_z17` | Input (3x) | FC04 read | uint16 |
| `0x004D` (77) — Z18 Dampers<br>`fault_z18` | Input (3x) | FC04 read | uint16 |
| `0x004E` (78) — Z19 Fan speed difference - basic ventilation<br>`fault_z19` | Input (3x) | FC04 read | uint16 |
| `0x004F` (79) — Z20 Fan speed difference too high<br>`fault_z20` | Input (3x) | FC04 read | uint16 |
| `0x0050` (80) — Z21 Post-heater frost protection<br>`fault_z21` | Input (3x) | FC04 read | uint16 |
| `0x0054` (84) — Total operating hours<br>`fan_total_hours` | Input (3x) | FC04 read | uint16 |
| `0x0056` (86) — Operating hours bypass<br>`bypass_hours` | Input (3x) | FC04 read | uint16 |
| `0x0058` (88) — Operating hours ventilation level 1<br>`fan_level_1_hours` | Input (3x) | FC04 read | uint16 |
