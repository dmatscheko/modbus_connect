# SolaX Power X3-Hybrid G4 — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/Solax_X3_Hybrid_G4.yaml`

## Primary source

- **SolaX — Energy Storage Inverter Modbus TCP & RTU Communication Protocol (Hybrid X1&X3-G4)** (V3.36, 2024-06-11)
- Source: [https://github.com/user-attachments/files/19076476/Solax.Hybrid_X1.X3-G4_ModbusTCP.RTU_V3.36-English_240611.1.pdf](https://github.com/user-attachments/files/19076476/Solax.Hybrid_X1.X3-G4_ModbusTCP.RTU_V3.36-English_240611.1.pdf)
- Source type: manufacturer-authored PDF, community-hosted (SolaX does not publish it publicly)
- Register addresses vs device file: verified — 0x1F use-mode, 0x42 export limit, 0x7C ARM/DSP + power-control, 0xEA peak-shaving, VPP/schedule; 0-based PDU, big-endian words
- Local copy: [`SolaX-Hybrid-X1X3-G4-ModbusTCPRTU-V3.36-EN-240611.pdf`](./SolaX-Hybrid-X1X3-G4-ModbusTCPRTU-V3.36-EN-240611.pdf) — 3.9 MB — primary source
- Local copy: [`caveats.md`](./caveats.md) — 1 KB
- Local copy: [`groups.md`](./groups.md) — 2 KB
- Local copy: [`SolaX-EnergyStorageInverter-MODBUS-Protocol-V001.02.pdf`](./SolaX-EnergyStorageInverter-MODBUS-Protocol-V001.02.pdf) — 3.0 MB

> SolaX does not publish its Modbus protocol publicly; this is the genuine SolaX-authored PDF (the revision homeassistant-solax-modbus references), redistributed via GitHub. A second doc, V001.02 (matches the device-file header ‘V1.02+’, lists X3-Hybrid G4 / G4 PRO / X1-Hybrid G4), is also in this folder. The inverter supports FC06 (write single) and FC16 (write multiple); the remote-control block requires FC16, and writes require the inverter unlocked.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 447 (Holding 264, Input 183) · plus 23 composite template entities

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x0000` (0) — Lock State<br>`lock_state` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 3 opts |
| `0x0000` (0) — serial _(internal)_ | Holding (4x) | FC03 read | string · 7 regs (14 chars) · swap byte |
| `0x0000` (0) — Sync RTC<br>`sync_rtc` | Holding (4x) | FC16 write-only | uint16 |
| `0x0007` (7) — Manufacturer<br>`manufacturer_name` | Holding (4x) | FC03 read | string · 7 regs (14 chars) |
| `0x000E` (14) — Model Number<br>`model_number` | Holding (4x) | FC03 read | string · 7 regs (14 chars) |
| `0x0015` (21) — Inverter ID Number<br>`inverter_id` | Holding (4x) | FC03 read | uint16 |
| `0x001C` (28) — System On<br>`system_on` | Holding (4x) | FC06 write-only | uint16 |
| `0x001C` (28) — System Off<br>`system_off` | Holding (4x) | FC06 write-only | uint16 |
| `0x001D` (29) — Safety code<br>`safety_code` | Holding (4x) | FC03 read | uint16 · enum · 49 opts |
| `0x001E` (30) — MateBox enabled<br>`matebox_enabled` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x001F` (31) — Charger Use Mode<br>`charger_use_mode` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 6 opts |
| `0x0020` (32) — Manual Mode Select<br>`manual_mode_select` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 3 opts |
| `0x0024` (36) — Battery Charge Max Current<br>`battery_charge_max_current` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · ×0.1 |
| `0x0025` (37) — Battery Discharge Max Current<br>`battery_discharge_max_current` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · ×0.1 |
| `0x0042` (66) — Export Control User Limit<br>`export_control_user_limit` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · ×10 |
| `0x0044` (68) — EPS Min SOC<br>`eps_min_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x0046` (70) — Measured power<br>`measured_power` | Holding (4x) | FC03 read | int32 · swap word |
| `0x0048` (72) — MPPT<br>`mppt` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x0056` (86) — Battery Awaken<br>`battery_awaken` | Holding (4x) | FC06 write-only | uint16 |
| `0x005A` (90) — Max PV Output Power<br>`max_pv_output_power` | Holding (4x) | FC03 read | uint16 |
| `0x005D` (93) — bias_power_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0061` (97) — Selfuse Discharge Min SOC<br>`selfuse_discharge_min_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x0062` (98) — Selfuse Night Charge Enable<br>`selfuse_night_charge_enable` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x0063` (99) — Selfuse Nightcharge Upper SOC<br>`selfuse_nightcharge_upper_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x0064` (100) — Feedin Nightcharge Upper SOC<br>`feedin_nightcharge_upper_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x0065` (101) — Feedin Discharge Min SOC<br>`feedin_discharge_min_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x0066` (102) — Backup Nightcharge Upper SOC<br>`backup_nightcharge_upper_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x0067` (103) — Backup Discharge Min SOC<br>`backup_discharge_min_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x0068` (104) — Charge Start 1<br>`charge_start_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x0069` (105) — Charge End 1<br>`charge_end_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x006A` (106) — Discharge Start 1<br>`discharge_start_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x006B` (107) — Discharge End 1<br>`discharge_end_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x006C` (108) — Charge and Discharge Period2 Enable<br>`charge_and_discharge_period2_enable` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x006D` (109) — Charge Start 2<br>`charge_start_2` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x006E` (110) — Charge End 2<br>`charge_end_2` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x006F` (111) — Discharge Start 2<br>`discharge_start_2` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x0070` (112) — Discharge End 2<br>`discharge_end_2` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x0071` (113) — Main Breaker Current Limit<br>`main_breaker_current_limit` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x007B` (123) — firmware_dsp _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x007C` (124) — Modbus Power Control (direct)<br>`modbus_power_control_direct` | Holding (4x) | FC16 write-only (forced write-multiple) | uint16 · enum · 10 opts |
| `0x007C` (124) — firmware_arm _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x007D` (125) — RemoteControl Target Set Type (mode 8/9; direct)<br>`remote_control_target_set_type_direct` | Holding (4x) | FC16 write-only (forced write-multiple) | uint16 · enum · 2 opts |
| `0x007E` (126) — Remotecontrol Active Power (mode 1; direct)<br>`remotecontrol_active_power_direct` | Holding (4x) | FC16 write-only | int32 · swap word |
| `0x007E` (126) — Inverter DSP hardware version<br>`firmware_DSP_hardware_version` | Holding (4x) | FC03 read | uint16 |
| `0x0080` (128) — Remotecontrol Reactive Power (mode 1; direct)<br>`remotecontrol_reactive_power_direct` | Holding (4x) | FC16 write-only | int32 · swap word |
| `0x0082` (130) — Remotecontrol Duration (mode 1; direct)<br>`remotecontrol_duration_direct` | Holding (4x) | FC06 write-only | uint16 |
| `0x0082` (130) — Modbus Protocol Version<br>`modbus_protocol_version` | Holding (4x) | FC03 read | uint16 |
| `0x0083` (131) — Remotecontrol Target SOC (mode 3; direct)<br>`remotecontrol_target_soc_direct` | Holding (4x) | FC06 write-only | uint16 |
| `0x0084` (132) — Remotecontrol Target Energy (mode 2; direct)<br>`remotecontrol_target_energy_direct` | Holding (4x) | FC16 write-only | int32 · swap word |
| `0x0084` (132) — Bootloader Version<br>`bootloader_version` | Holding (4x) | FC03 read | uint16 |
| `0x0085` (133) — rtc_second _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0086` (134) — Remotecontrol Charge/Discharge Power (mode 2/3; direct)<br>`remotecontrol_charge_discharge_power_direct` | Holding (4x) | FC16 write-only | int32 · swap word |
| `0x0086` (134) — rtc_minute _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0087` (135) — rtc_hour _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0088` (136) — Remotecontrol TimeOut (mode 1-7; direct)<br>`remotecontrol_timeout_direct` | Holding (4x) | FC16 write-only (forced write-multiple) | uint16 |
| `0x0088` (136) — rtc_day _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0089` (137) — Remotecontrol Push Mode Power (mode 4; direct)<br>`remotecontrol_push_mode_power_direct` | Holding (4x) | FC16 write-only | int32 · swap word |
| `0x0089` (137) — rtc_month _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x008A` (138) — rtc_year _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x008B` (139) — charger_use_mode_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 6 opts |
| `0x008C` (140) — manual_mode_select_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 3 opts |
| `0x008D` (141) — Pgrid Bias<br>`pgrid_bias` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 3 opts |
| `0x008D` (141) — Battery Type<br>`battery_type` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x008E` (142) — EPS Restart SOC<br>`eps_restart_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x008E` (142) — Battery Charge Float Voltage<br>`battery_charge_float_voltage` | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x008F` (143) — Battery Discharge Cut Off Voltage<br>`battery_discharge_cut_off_voltage` | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x0090` (144) — battery_charge_max_current_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x0091` (145) — battery_discharge_max_current_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x0093` (147) — selfuse_night_charge_enable_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · mask 0xFF · enum · 2 opts |
| `0x0093` (147) — selfuse_discharge_min_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · mask 0xFF00 |
| `0x0094` (148) — selfuse_nightcharge_upper_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0095` (149) — feedin_discharge_min_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · mask 0xFF |
| `0x0095` (149) — feedin_nightcharge_upper_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · mask 0xFF00 |
| `0x0096` (150) — backup_discharge_min_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · mask 0xFF |
| `0x0096` (150) — backup_nightcharge_upper_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · mask 0xFF00 |
| `0x0097` (151) — charge_start_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x0098` (152) — Shadow Fix Function Level PV2 (GMPPT)<br>`shadow_fix_function_level_pv2_gmppt` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 4 opts |
| `0x0098` (152) — charge_end_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x0099` (153) — HotStandBy<br>`hotstandby` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x0099` (153) — discharge_start_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x009A` (154) — Extend BMS Setting<br>`extend_bms_setting` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x009A` (154) — discharge_end_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x009B` (155) — charge_and_discharge_period2_enable_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x009C` (156) — Shadow Fix Function Level PV1 (GMPPT)<br>`shadow_fix_function_level_pv1_gmppt` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 4 opts |
| `0x009C` (156) — charge_start_2_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x009D` (157) — charge_end_2_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x009E` (158) — Phase Power Balance X3<br>`phase_power_balance_x3` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x009E` (158) — discharge_start_2_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x009F` (159) — discharge_end_2_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x00A0` (160) — RemoteControl Power Control Mode (mode 8/9; direct)<br>`remote_control_power_control_mode_direct` | Holding (4x) | FC16 write-only (forced write-multiple) | uint16 · enum · 3 opts |
| `0x00A0` (160) — eps_restart_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x00A1` (161) — hotstandby_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x00A1` (161) — Power Control Mode Target Set Type (mode 8/9; direct)<br>`power_control_mode_target_set_type_direct` | Holding (4x) | FC16 write-only (forced write-multiple) | uint16 · enum · 2 opts |
| `0x00A2` (162) — extend_bms_setting_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x00A2` (162) — Remotecontrol PV Power Limit (mode 8/9, direct)<br>`remotecontrol_pv_power_limit_direct` | Holding (4x) | FC16 write-only | uint32 · swap word |
| `0x00A3` (163) — battery_heating_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x00A4` (164) — Meter 1 Direction<br>`meter_1_direction` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00A4` (164) — Remotecontrol Push Mode Power (mode 8/9; direct)<br>`remotecontrol_push_mode_power_8_9_direct` | Holding (4x) | FC16 write-only | int32 · swap word |
| `0x00A4` (164) — battery_heating_start_time_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x00A5` (165) — Meter 2 Direction<br>`meter_2_direction` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00A5` (165) — battery_heating_end_time_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x00A6` (166) — Discharge Cut Off Point Different<br>`discharge_cut_off_point_different` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00A6` (166) — Remotecontrol Duration (mode 8; direct)<br>`remotecontrol_duration_8_direct` | Holding (4x) | FC16 write-only (forced write-multiple) | uint16 |
| `0x00A6` (166) — Remotecontrol Target SOC (mode 9; direct)<br>`remotecontrol_target_soc_9_direct` | Holding (4x) | FC16 write-only (forced write-multiple) | uint16 |
| `0x00A6` (166) — battery_heating_start_time_2_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x00A7` (167) — Remotecontrol TimeOut (mode 8/9; direct)<br>`remotecontrol_timeout_8_9_direct` | Holding (4x) | FC16 write-only (forced write-multiple) | uint16 |
| `0x00A7` (167) — battery_heating_end_time_2_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x00AA` (170) — Registration Code Pocket<br>`registration_code_pocket` | Holding (4x) | FC03 read | string · 5 regs (10 chars) |
| `0x00B2` (178) — pgrid_bias_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 3 opts |
| `0x00B3` (179) — fast_ct_check_enable_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x00B4` (180) — vpp_exit_idle_enable_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x00B4` (180) — Lease Mode<br>`lease_mode` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00B5` (181) — Device Lock<br>`device_lock` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00B5` (181) — Export Control Factory Limit<br>`export_control_factory_limit` | Holding (4x) | FC03 read | uint16 |
| `0x00B6` (182) — Manual Mode Control<br>`manual_mode_control` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00B6` (182) — export_control_user_limit_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · ×10 |
| `0x00B7` (183) — Feedin On Power<br>`feedin_on_power` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00B7` (183) — EPS Mute<br>`eps_mute` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x00B8` (184) — eps_min_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x00B8` (184) — Switch On SOC<br>`switch_on_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00B9` (185) — Consume Off Power<br>`consume_off_power` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00B9` (185) — EPS Set Frequency<br>`eps_set_frequency` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x00BA` (186) — Switch Off SOC<br>`switch_off_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00BA` (186) — Inverter Rated Output Power<br>`inverter_power_type` | Holding (4x) | FC03 read | uint16 |
| `0x00BB` (187) — Minimum Per On Signal<br>`minimum_per_on_signal` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00BB` (187) — Language<br>`language` | Holding (4x) | FC03 read | uint16 · enum · 8 opts |
| `0x00BC` (188) — mppt_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x00BC` (188) — Maximum Per Day On<br>`maximum_per_day_on` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00BD` (189) — Schedule<br>`schedule` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00BE` (190) — Work Start Time 1<br>`work_start_time_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x00BF` (191) — Work End Time 1<br>`work_end_time_1` | Holding (4x) | FC03 read · FC06 write | time hh:mm |
| `0x00C0` (192) — Work Start Time 2<br>`work_start_time_2` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x00C1` (193) — Work End Time 2<br>`work_end_time_2` | Holding (4x) | FC03 read · FC06 write | time hh:mm |
| `0x00C2` (194) — Work Mode<br>`work_mode` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 3 opts |
| `0x00C3` (195) — Dry Contact Mode<br>`dry_contact_mode` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00C4` (196) — Selfuse Mode Backup<br>`selfuse_mode_backup` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00C5` (197) — Selfuse Backup SOC<br>`selfuse_backup_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00C6` (198) — Parallel Setting<br>`parallel_setting` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 3 opts |
| `0x00C7` (199) — Generator Control<br>`generator_control` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 3 opts |
| `0x00C8` (200) — Generator Max Charge<br>`generator_max_charge` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · ×10 |
| `0x00CF` (207) — Battery Heating<br>`battery_heating` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00D0` (208) — Battery Heating Start Time 1<br>`battery_heating_start_time_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x00D1` (209) — Battery Heating End Time 1<br>`battery_heating_end_time_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x00D2` (210) — Battery Heating Start Time 2<br>`battery_heating_start_time_2` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x00D3` (211) — Battery Heating End Time 2<br>`battery_heating_end_time_2` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x00D7` (215) — main_breaker_current_limit_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x00E0` (224) — Battery Charge Upper SOC<br>`battery_charge_upper_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00E1` (225) — Battery to EV Charger<br>`battery_to_ev_charger` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00E3` (227) — Generator Start Method<br>`generator_start_method` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00E4` (228) — Generator Switch On SOC<br>`generator_switch_on_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00E5` (229) — Generator Switch Off SOC<br>`generator_switch_off_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00E6` (230) — Generator Max Run Time<br>`generator_max_run_time` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00E7` (231) — Generator Min Rest Time<br>`generator_min_rest_time` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00E8` (232) — Generator Start Time 1<br>`generator_start_time_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x00E9` (233) — Generator Stop Time 1<br>`generator_stop_time_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x00EA` (234) — PeakShaving Discharge Start Time 1<br>`peakshaving_discharge_start_time_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x00EB` (235) — PeakShaving Discharge Stop Time 1<br>`peakshaving_discharge_stop_time_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x00EC` (236) — PeakShaving Discharge Start Time 2<br>`peakshaving_discharge_start_time_2` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x00ED` (237) — PeakShaving Discharge Stop Time 2<br>`peakshaving_discharge_stop_time_2` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x00EE` (238) — PeakShaving Discharge Limit 1<br>`peakshaving_discharge_limit_1` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · ×0.1 |
| `0x00EF` (239) — PeakShaving Discharge Limit 2<br>`peakshaving_discharge_limit_2` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · ×0.1 |
| `0x00F0` (240) — PeakShaving Charge from Grid<br>`peakshaving_charge_from_grid` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00F1` (241) — PeakShaving Charge Limit<br>`peakshaving_charge_limit` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00F2` (242) — PeakShaving Max SOC<br>`peakshaving_max_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00F3` (243) — PeakShaving Reserved SOC<br>`peakshaving_reserved_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00F4` (244) — VPP Exit Idle Enable<br>`vpp_exit_idle_enable` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00F5` (245) — Fast CT Check Enable<br>`fast_ct_check_enable` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00F9` (249) — EV Charger Address<br>`ev_charger_address` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00FB` (251) — Adapt Box G2 Address<br>`adapt_box_g2_address` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x00FD` (253) — CT Cycle Detection<br>`ct_cycle_detection` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x00FE` (254) — EPS Mode without Battery<br>`eps_mode_without_battery` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x0100` (256) — Generator Charge Start Time 1<br>`generator_charge_start_time_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x0101` (257) — Generator Charge Stop Time 1<br>`generator_charge_stop_time_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x0102` (258) — Generator Discharge Start Time 1<br>`generator_discharge_start_time_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x0102` (258) — DRM Function Enable<br>`drm_function_enable` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0103` (259) — Generator Discharge Stop Time 1<br>`generator_discharge_stop_time_1` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x0103` (259) — CT Type<br>`ct_type` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0104` (260) — Generator Time 2<br>`generator_time_2` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x0104` (260) — shadow_fix_function_level_pv1_gmppt_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 4 opts |
| `0x0105` (261) — Generator Charge Start Time 2<br>`generator_charge_start_time_2` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x0105` (261) — Machine Type<br>`machine_type` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0106` (262) — phase_power_balance_x3_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0106` (262) — Generator Charge Stop Time 2<br>`generator_charge_stop_time_2` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x0107` (263) — Generator Discharge Start Time 2<br>`generator_discharge_start_time_2` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x0107` (263) — Machine Style<br>`machine_style` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0108` (264) — Generator Discharge Stop Time 2<br>`generator_discharge_stop_time_2` | Holding (4x) | FC06 write · read-back elsewhere | time hh:mm |
| `0x0108` (264) — Meter Function<br>`meter_function` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0109` (265) — Generator Charge<br>`generator_charge` | Holding (4x) | FC06 write · read-back elsewhere | uint16 · enum · 2 opts |
| `0x0109` (265) — Meter 1 ID<br>`meter_1_id` | Holding (4x) | FC03 read | uint16 |
| `0x010A` (266) — Generator Charge SOC<br>`generator_charge_soc` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x010A` (266) — Meter 2 ID<br>`meter_2_id` | Holding (4x) | FC03 read | uint16 |
| `0x010B` (267) — meter_1_direction_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x010C` (268) — meter_2_direction_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x010E` (270) — battery_charge_upper_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x010E` (270) — Generator Min Power<br>`generator_min_power` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x010F` (271) — battery_to_ev_charger_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0111` (273) — discharge_cut_off_point_different_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0113` (275) — Discharge Cut Off Voltage Grid Mode<br>`discharge_cut_off_voltage_grid_mode` | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x0114` (276) — shadow_fix_function_level_pv2_gmppt_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 4 opts |
| `0x0115` (277) — CT Meter Setting<br>`ct_meter_setting` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0116` (278) — FVRT Function<br>`fvrt_function` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0117` (279) — FVRT Vac Upper<br>`fvrt_vac_upper` | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x0118` (280) — FVRT Vac Lower<br>`fvrt_vac_lower` | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x0119` (281) — Bias Power<br>`bias_power` | Holding (4x) | FC06 write · read-back elsewhere | uint16 |
| `0x011B` (283) — PV Connection Mode<br>`pv_connection_mode` | Holding (4x) | FC03 read | uint16 |
| `0x011C` (284) — Shut Down<br>`shut_down` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x011D` (285) — Micro Grid<br>`micro_grid` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x011E` (286) — selfuse_mode_backup_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x011F` (287) — selfuse_backup_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0120` (288) — lease_mode_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0121` (289) — device_lock_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0122` (290) — manual_mode_control_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0123` (291) — feedin_on_power_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0124` (292) — switch_on_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0125` (293) — consume_off_power_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0126` (294) — switch_off_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0127` (295) — minimum_per_on_signal_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0128` (296) — maximum_per_day_on_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0129` (297) — schedule_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x012A` (298) — work_start_time_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x012C` (300) — work_start_time_2_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x012E` (302) — work_mode_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 3 opts |
| `0x012F` (303) — dry_contact_mode_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0130` (304) — parallel_setting_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 3 opts |
| `0x0131` (305) — generator_control_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 3 opts |
| `0x0132` (306) — generator_max_charge_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · ×10 |
| `0x0140` (320) — generator_start_method_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0141` (321) — generator_switch_on_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0142` (322) — generator_switch_off_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0143` (323) — generator_max_run_time_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0145` (325) — generator_min_rest_time_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0146` (326) — generator_start_time_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x0147` (327) — generator_stop_time_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x0148` (328) — generator_min_power_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x014F` (335) — peakshaving_discharge_start_time_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x0150` (336) — peakshaving_discharge_stop_time_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x0151` (337) — peakshaving_discharge_start_time_2_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x0152` (338) — peakshaving_discharge_stop_time_2_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x0153` (339) — peakshaving_discharge_limit_1_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x0154` (340) — peakshaving_discharge_limit_2_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x0155` (341) — peakshaving_charge_from_grid_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0156` (342) — peakshaving_charge_limit_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0157` (343) — peakshaving_max_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0158` (344) — peakshaving_reserved_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x015C` (348) — ev_charger_address_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x015E` (350) — adapt_box_g2_address_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0160` (352) — ct_cycle_detection_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0161` (353) — eps_mode_without_battery_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0162` (354) — generator_charge_start_time_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x0163` (355) — generator_charge_stop_time_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x0164` (356) — generator_discharge_start_time_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x0165` (357) — generator_discharge_stop_time_1_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x0166` (358) — generator_time_2_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0167` (359) — generator_charge_start_time_2_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x0168` (360) — generator_charge_stop_time_2_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x0169` (361) — generator_discharge_start_time_2_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x016A` (362) — generator_discharge_stop_time_2_readback _(internal)_ | Holding (4x) | FC03 read | time hh:mm · swap byte |
| `0x016B` (363) — generator_charge_readback _(internal)_ | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x016C` (364) — generator_charge_soc_readback _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x01A0` (416) — Remotecontrol Readback Mode<br>`remotecontrol_readback_mode` | Holding (4x) | FC03 read | uint16 · enum · 10 opts |
| `0x01A2` (418) — Remotecontrol Mode 8 PV Power Limit Readback<br>`remotecontrol_mode8_pv_power_limit_readback` | Holding (4x) | FC03 read | uint32 · swap word |
| `0x01A4` (420) — Remotecontrol Mode 8 Battery Power Target Readback<br>`remotecontrol_mode8_battery_power_target_readback` | Holding (4x) | FC03 read | int32 · swap word |
| `0x01A6` (422) — Remotecontrol Mode 8 Timeout Readback<br>`remotecontrol_mode8_timeout_readback` | Holding (4x) | FC03 read | uint16 |
| `0x01A7` (423) — Remotecontrol Mode 8 Next Motion Readback<br>`remotecontrol_mode8_next_motion_readback` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0000` (0) — Inverter Voltage<br>`inverter_voltage` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0001` (1) — Inverter Current<br>`inverter_current` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0002` (2) — Inverter Power<br>`inverter_power` | Input (3x) | FC04 read | int16 |
| `0x0003` (3) — PV Voltage 1<br>`pv_voltage_1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0004` (4) — PV Voltage 2<br>`pv_voltage_2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0005` (5) — PV Current 1<br>`pv_current_1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0006` (6) — PV Current 2<br>`pv_current_2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0007` (7) — Inverter Frequency<br>`inverter_frequency` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0008` (8) — Inverter Temperature<br>`inverter_temperature` | Input (3x) | FC04 read | int16 |
| `0x0009` (9) — Run Mode<br>`run_mode` | Input (3x) | FC04 read | uint16 · enum · 20 opts |
| `0x000A` (10) — PV Power 1<br>`pv_power_1` | Input (3x) | FC04 read | uint16 |
| `0x000B` (11) — PV Power 2<br>`pv_power_2` | Input (3x) | FC04 read | uint16 |
| `0x0013` (19) — Time Count Down<br>`time_count_down` | Input (3x) | FC04 read | uint16 · ×0.001 |
| `0x0014` (20) — Battery Voltage Charge<br>`battery_voltage_charge` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0015` (21) — Battery Current Charge<br>`battery_current_charge` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0016` (22) — Battery Power Charge<br>`battery_power_charge` | Input (3x) | FC04 read | int16 |
| `0x0017` (23) — BMS Connect State<br>`bms_connect_state` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x0018` (24) — Battery Temperature<br>`battery_temperature` | Input (3x) | FC04 read | int16 |
| `0x0019` (25) — BDC Status<br>`bdc_status` | Input (3x) | FC04 read | uint16 · enum · 3 opts |
| `0x001A` (26) — Grid Status<br>`grid_status` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x001B` (27) — MPPT Count<br>`mppt_count` | Input (3x) | FC04 read | uint16 |
| `0x001C` (28) — Battery Capacity<br>`battery_capacity` | Input (3x) | FC04 read | uint16 |
| `0x001D` (29) — Battery Output Energy Total<br>`battery_output_energy_total` | Input (3x) | FC04 read | uint32 · swap word · ×0.1 |
| `0x0020` (32) — Battery Output Energy Today<br>`battery_output_energy_today` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0021` (33) — Battery Input Energy Total<br>`battery_input_energy_total` | Input (3x) | FC04 read | uint32 · swap word · ×0.1 |
| `0x0023` (35) — Battery Input Energy Today<br>`battery_input_energy_today` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0024` (36) — Battery Charge Max Current<br>`bms_charge_max_current` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0025` (37) — Battery Discharge Max Current<br>`bms_discharge_max_current` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0026` (38) — Battery Total Energy<br>`bms_battery_capacity` | Input (3x) | FC04 read | uint32 · swap word |
| `0x0032` (50) — PV Power Total<br>`pv_power_total` | Input (3x) | FC04 read | uint32 · swap word |
| `0x0034` (52) — Total On-Grid Power<br>`ongrid_power_total` | Input (3x) | FC04 read | int32 · swap word |
| `0x0036` (54) — Total Off-Grid Power<br>`offgrid_power_total` | Input (3x) | FC04 read | int32 · swap word |
| `0x003A` (58) — Battery System Installed Capacity<br>`battery_system_installed_capacity` | Input (3x) | FC04 read | uint32 · swap word |
| `0x0048` (72) — Grid Export Total<br>`grid_export_total` | Input (3x) | FC04 read | uint32 · swap word · ×0.01 |
| `0x004A` (74) — Grid Import Total<br>`grid_import_total` | Input (3x) | FC04 read | uint32 · swap word · ×0.01 |
| `0x004F` (79) — EPS Frequency<br>`eps_frequency` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0050` (80) — Today's Yield<br>`today_s_yield` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0052` (82) — Total Yield<br>`total_yield` | Input (3x) | FC04 read | uint32 · swap word · ×0.1 |
| `0x0054` (84) — lock_state_readback _(internal)_ | Input (3x) | FC04 read | uint16 · enum · 3 opts |
| `0x0066` (102) — Bus Volt<br>`bus_volt` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0067` (103) — DC Fault Val<br>`dc_fault_val` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0068` (104) — Overload Fault Val<br>`overload_fault_val` | Input (3x) | FC04 read | uint16 |
| `0x0069` (105) — Battery Volt Fault Val<br>`battery_volt_fault_val` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x006A` (106) — Inverter Voltage L1<br>`inverter_voltage_l1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x006B` (107) — Inverter Current L1<br>`inverter_current_l1` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x006C` (108) — Inverter Power L1<br>`inverter_power_l1` | Input (3x) | FC04 read | int16 |
| `0x006D` (109) — Inverter Frequency L1<br>`inverter_frequency_l1` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x006E` (110) — Inverter Voltage L2<br>`inverter_voltage_l2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x006F` (111) — Inverter Current L2<br>`inverter_current_l2` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0070` (112) — Inverter Power L2<br>`inverter_power_l2` | Input (3x) | FC04 read | int16 |
| `0x0071` (113) — Inverter Frequency L2<br>`inverter_frequency_l2` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0072` (114) — Inverter Voltage L3<br>`inverter_voltage_l3` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0073` (115) — Inverter Current L3<br>`inverter_current_l3` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0074` (116) — Inverter Power L3<br>`inverter_power_l3` | Input (3x) | FC04 read | int16 |
| `0x0075` (117) — Inverter Frequency L3<br>`inverter_frequency_l3` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0076` (118) — EPS Voltage L1<br>`eps_voltage_l1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0077` (119) — EPS Current L1<br>`eps_current_l1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0078` (120) — EPS Power Active L1<br>`eps_power_active_l1` | Input (3x) | FC04 read | uint16 |
| `0x0079` (121) — EPS Power L1<br>`eps_power_l1` | Input (3x) | FC04 read | uint16 |
| `0x007A` (122) — EPS Voltage L2<br>`eps_voltage_l2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x007B` (123) — EPS Current L2<br>`eps_current_l2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x007C` (124) — EPS Power Active L2<br>`eps_power_active_l2` | Input (3x) | FC04 read | uint16 |
| `0x007D` (125) — EPS Power L2<br>`eps_power_l2` | Input (3x) | FC04 read | uint16 |
| `0x007E` (126) — EPS Voltage L3<br>`eps_voltage_l3` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x007F` (127) — EPS Current L3<br>`eps_current_l3` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0080` (128) — EPS Power Active L3<br>`eps_power_active_l3` | Input (3x) | FC04 read | uint16 |
| `0x0081` (129) — EPS Power L3<br>`eps_power_l3` | Input (3x) | FC04 read | uint16 |
| `0x0082` (130) — Measured Power L1<br>`measured_power_l1` | Input (3x) | FC04 read | int32 · swap word |
| `0x0084` (132) — Measured Power L2<br>`measured_power_l2` | Input (3x) | FC04 read | int32 · swap word |
| `0x0086` (134) — Measured Power L3<br>`measured_power_l3` | Input (3x) | FC04 read | int32 · swap word |
| `0x0088` (136) — Grid Mode Runtime<br>`grid_mode_runtime` | Input (3x) | FC04 read | int32 · swap word · ×0.1 |
| `0x008A` (138) — EPS Mode Runtime<br>`eps_mode_runtime` | Input (3x) | FC04 read | int32 · swap word · ×0.1 |
| `0x008E` (142) — EPS Yield Total<br>`eps_yield_total` | Input (3x) | FC04 read | uint32 · swap word · ×0.1 |
| `0x0090` (144) — EPS Yield Today<br>`eps_yield_today` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0091` (145) — E Charge Today<br>`e_charge_today` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0092` (146) — E Charge Total<br>`e_charge_total` | Input (3x) | FC04 read | uint32 · swap word · ×0.1 |
| `0x0094` (148) — Total Solar Energy<br>`total_solar_energy` | Input (3x) | FC04 read | uint32 · swap word · ×0.1 |
| `0x0096` (150) — Today's Solar Energy<br>`today_s_solar_energy` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0098` (152) — Today's Export Energy<br>`today_s_export_energy` | Input (3x) | FC04 read | uint32 · swap word · ×0.01 |
| `0x009A` (154) — Today's Import Energy<br>`today_s_import_energy` | Input (3x) | FC04 read | uint32 · swap word · ×0.01 |
| `0x00A0` (160) — EV Charger Communication State<br>`ev_charger_communication_state` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x00A1` (161) — Adapter Box Communication State<br>`adapt_box_communication_state` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x00A2` (162) — Battery Max Charge Power<br>`battery_max_charge_power` | Input (3x) | FC04 read | uint32 · swap word |
| `0x00A4` (164) — Battery Max Discharge Power<br>`battery_max_discharge_power` | Input (3x) | FC04 read | uint32 · swap word |
| `0x00A8` (168) — Meter 2 Measured Power<br>`meter_2_measured_power` | Input (3x) | FC04 read | int32 · swap word |
| `0x00AA` (170) — Meter 2 Export Total<br>`meter_2_export_total` | Input (3x) | FC04 read | uint32 · swap word · ×0.01 |
| `0x00AC` (172) — Meter 2 Import Total<br>`meter_2_import_total` | Input (3x) | FC04 read | uint32 · swap word · ×0.01 |
| `0x00AE` (174) — Meter 2 Export Today<br>`meter_2_export_today` | Input (3x) | FC04 read | uint32 · swap word · ×0.01 |
| `0x00B0` (176) — Meter 2 Import Today<br>`meter_2_import_today` | Input (3x) | FC04 read | uint32 · swap word · ×0.01 |
| `0x00B2` (178) — Meter 2 Measured Power L1<br>`meter_2_measured_power_l1` | Input (3x) | FC04 read | int32 · swap word |
| `0x00B4` (180) — Meter 2 Measured Power L2<br>`meter_2_measured_power_l2` | Input (3x) | FC04 read | int32 · swap word |
| `0x00B6` (182) — Meter 2 Measured Power L3<br>`meter_2_measured_power_l3` | Input (3x) | FC04 read | int32 · swap word |
| `0x00B8` (184) — Meter 1 Communication State<br>`meter_1_communication_state` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x00B9` (185) — Meter 2 Communication State<br>`meter_2_communication_state` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x00BA` (186) — Battery Temp High<br>`battery_temp_high` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x00BB` (187) — Battery Temp Low<br>`battery_temp_low` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x00BC` (188) — Cell Voltage High<br>`cell_voltage_high` | Input (3x) | FC04 read | uint16 · ×0.001 |
| `0x00BD` (189) — Cell Voltage Low<br>`cell_voltage_low` | Input (3x) | FC04 read | uint16 · ×0.001 |
| `0x00BF` (191) — Battery State of Health<br>`battery_soh` | Input (3x) | FC04 read | uint16 |
| `0x00C4` (196) — Grid Power Factor Total<br>`grid_power_factor_total` | Input (3x) | FC04 read | int16 |
| `0x00C5` (197) — Grid Power Factor L1<br>`grid_power_factor_l1` | Input (3x) | FC04 read | int16 |
| `0x00C6` (198) — Grid Power Factor L2<br>`grid_power_factor_l2` | Input (3x) | FC04 read | int16 |
| `0x00C7` (199) — Grid Power Factor L3<br>`grid_power_factor_l3` | Input (3x) | FC04 read | int16 |
| `0x00C8` (200) — Grid Frequency<br>`grid_frequency` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x00C9` (201) — Grid Voltage<br>`grid_voltage` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x00CA` (202) — Grid Voltage L1<br>`grid_voltage_l1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x00CB` (203) — Grid Voltage L2<br>`grid_voltage_l2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x00CC` (204) — Grid Voltage L3<br>`grid_voltage_l3` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x00CD` (205) — Grid Current Total<br>`grid_current_total` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x00CE` (206) — Grid Current L1<br>`grid_current_l1` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x00CF` (207) — Grid Current L2<br>`grid_current_l2` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x00D0` (208) — Grid Current L3<br>`grid_current_l3` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x00D2` (210) — Grid Reactive Power Total<br>`grid_reactive_power_total` | Input (3x) | FC04 read | int32 · swap word |
| `0x00D4` (212) — Grid Reactive Power L3<br>`grid_reactive_power_l3` | Input (3x) | FC04 read | int32 · swap word |
| `0x00DE` (222) — Grid Reactive Power L1<br>`grid_reactive_power_l1` | Input (3x) | FC04 read | int32 · swap word |
| `0x00E0` (224) — Grid Reactive Power L2<br>`grid_reactive_power_l2` | Input (3x) | FC04 read | int32 · swap word |
| `0x0100` (256) — Modbus Power Control<br>`modbus_power_control` | Input (3x) | FC04 read | uint16 · enum · 10 opts |
| `0x0101` (257) — Target Finish Flag<br>`target_finish_flag` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x0102` (258) — Active Power Target<br>`active_power_target` | Input (3x) | FC04 read | int32 · swap word |
| `0x0104` (260) — Reactive Power Target<br>`reactive_power_target` | Input (3x) | FC04 read | int32 · swap word |
| `0x0106` (262) — Active Power Real<br>`active_power_real` | Input (3x) | FC04 read | int32 · swap word |
| `0x0108` (264) — Reactive Power Real<br>`reactive_power_real` | Input (3x) | FC04 read | int32 · swap word |
| `0x010A` (266) — Active Power Upper<br>`active_power_upper` | Input (3x) | FC04 read | int32 · swap word |
| `0x010C` (268) — Active Power Lower<br>`active_power_lower` | Input (3x) | FC04 read | int32 · swap word |
| `0x010E` (270) — Reactive Power Upper<br>`reactive_power_upper` | Input (3x) | FC04 read | int32 · swap word |
| `0x0110` (272) — Reactive Power Lower<br>`reactive_power_lower` | Input (3x) | FC04 read | int32 · swap word |
| `0x0114` (276) — Charge Discharge Power<br>`charge_discharge_power` | Input (3x) | FC04 read | int32 · swap word |
| `0x0116` (278) — Chargeable Battery Energy<br>`chargeable_battery_capacity` | Input (3x) | FC04 read | uint32 · swap word |
| `0x0118` (280) — Remaining Battery Energy<br>`remaining_battery_capacity` | Input (3x) | FC04 read | uint32 · swap word |
| `0x01DD` (477) — PM Inverter Count<br>`pm_inverter_count` | Input (3x) | FC04 read | uint16 |
| `0x01E0` (480) — PM ActivePower L1<br>`pm_activepower_l1` | Input (3x) | FC04 read | int32 · swap word |
| `0x01E2` (482) — PM ActivePower L2<br>`pm_activepower_l2` | Input (3x) | FC04 read | int32 · swap word |
| `0x01E4` (484) — PM ActivePower L3<br>`pm_activepower_l3` | Input (3x) | FC04 read | int32 · swap word |
| `0x01E6` (486) — PM Reactive or ApparentPower L1<br>`pm_reactive_or_apparentpower_l1` | Input (3x) | FC04 read | int32 · swap word |
| `0x01E8` (488) — PM Reactive or ApparentPower L2<br>`pm_reactive_or_apparentpower_l2` | Input (3x) | FC04 read | int32 · swap word |
| `0x01EA` (490) — PM Reactive or ApparentPower L3<br>`pm_reactive_or_apparentpower_l3` | Input (3x) | FC04 read | int32 · swap word |
| `0x01EC` (492) — PM Inverter Current L1<br>`pm__current_l1` | Input (3x) | FC04 read | int32 · swap word · ×0.1 |
| `0x01EE` (494) — PM Inverter Current L2<br>`pm__current_l2` | Input (3x) | FC04 read | int32 · swap word · ×0.1 |
| `0x01F0` (496) — PM Inverter Current L3<br>`pm__current_l3` | Input (3x) | FC04 read | int32 · swap word · ×0.1 |
| `0x01F2` (498) — PM PV Power 1<br>`pm_pv_power_1` | Input (3x) | FC04 read | uint32 · swap word |
| `0x01F4` (500) — PM PV Power 2<br>`pm_pv_power_2` | Input (3x) | FC04 read | uint32 · swap word |
| `0x01F6` (502) — PM PV Current 1<br>`pm_pv_current_1` | Input (3x) | FC04 read | uint32 · swap word · ×0.1 |
| `0x01F8` (504) — PM PV Current 2<br>`pm_pv_current_2` | Input (3x) | FC04 read | uint32 · swap word · ×0.1 |
| `0x01FA` (506) — PM Battery Power Charge<br>`pm_battery_power_charge` | Input (3x) | FC04 read | int32 · swap word |
| `0x01FC` (508) — PM Battery Current Charge<br>`pm_battery_current_charge` | Input (3x) | FC04 read | int32 · swap word · ×0.01 |
| `0x0204` (516) — PM I2 ActivePower L1<br>`pm_i2_activepower_l1` | Input (3x) | FC04 read | int16 |
| `0x0205` (517) — PM I2 ActivePower L2<br>`pm_i2_activepower_l2` | Input (3x) | FC04 read | int16 |
| `0x0206` (518) — PM I2 ActivePower L3<br>`pm_i2_activepower_l3` | Input (3x) | FC04 read | int16 |
| `0x0207` (519) — PM I2 Reactive or ApparentPower L1<br>`pm_i2_reactive_or_apparentpower_l1` | Input (3x) | FC04 read | int16 |
| `0x0208` (520) — PM I2 Reactive or ApparentPower L2<br>`pm_i2_reactive_or_apparentpower_l2` | Input (3x) | FC04 read | int16 |
| `0x0209` (521) — PM I2 Reactive or ApparentPower L3<br>`pm_i2_reactive_or_apparentpower_l3` | Input (3x) | FC04 read | int16 |
| `0x020A` (522) — PM I2 Inverter Current L1<br>`pm_i2_current_l1` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x020B` (523) — PM I2 Inverter Current L2<br>`pm_i2_current_l2` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x020C` (524) — PM I2 Inverter Current L3<br>`pm_i2_current_l3` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x020D` (525) — PM I2 PV Power 1<br>`pm_i2_pv_power_1` | Input (3x) | FC04 read | uint16 |
| `0x020E` (526) — PM I2 PV Power 2<br>`pm_i2_pv_power_2` | Input (3x) | FC04 read | uint16 |
| `0x020F` (527) — PM I2 PV Voltage 1<br>`pm_i2_pv_voltage_1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0210` (528) — PM I2 PV Voltage 2<br>`pm_i2_pv_voltage_2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0211` (529) — PM I2 PV Current 1<br>`pm_i2_pv_current_1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0212` (530) — PM I2 PV Current 2<br>`pm_i2_pv_current_2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0213` (531) — PM I2 Battery Power Charge<br>`pm_i2_battery_power_charge` | Input (3x) | FC04 read | int16 |
| `0x0214` (532) — PM I2 Battery Voltage Charge<br>`pm_i2_battery_voltage_charge` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0215` (533) — PM I2 Battery Current Charge<br>`pm_i2_battery_current_charge` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0219` (537) — PM I2 Battery Capacity<br>`pm_i2_battery_capacity_charge` | Input (3x) | FC04 read | uint16 |
| `0x021E` (542) — PM I3 ActivePower L1<br>`pm_i3_activepower_l1` | Input (3x) | FC04 read | int16 |
| `0x021F` (543) — PM I3 ActivePower L2<br>`pm_i3_activepower_l2` | Input (3x) | FC04 read | int16 |
| `0x0220` (544) — PM I3 ActivePower L3<br>`pm_i3_activepower_l3` | Input (3x) | FC04 read | int16 |
| `0x0221` (545) — PM I3 Reactive or ApparentPower L1<br>`pm_i3_reactive_or_apparentpower_l1` | Input (3x) | FC04 read | int16 |
| `0x0222` (546) — PM I3 Reactive or ApparentPower L2<br>`pm_i3_reactive_or_apparentpower_l2` | Input (3x) | FC04 read | int16 |
| `0x0223` (547) — PM I3 Reactive or ApparentPower L3<br>`pm_i3_reactive_or_apparentpower_l3` | Input (3x) | FC04 read | int16 |
| `0x0224` (548) — PM I3 Inverter Current L1<br>`pm_i3_current_l1` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0225` (549) — PM I3 Inverter Current L2<br>`pm_i3_current_l2` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0226` (550) — PM I3 Inverter Current L3<br>`pm_i3_current_l3` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0227` (551) — PM I3 PV Power 1<br>`pm_i3_pv_power_1` | Input (3x) | FC04 read | uint16 |
| `0x0228` (552) — PM I3 PV Power 2<br>`pm_i3_pv_power_2` | Input (3x) | FC04 read | uint16 |
| `0x0229` (553) — PM I3 PV Voltage 1<br>`pm_i3_pv_voltage_1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x022A` (554) — PM I3 PV Voltage 2<br>`pm_i3_pv_voltage_2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x022B` (555) — PM I3 PV Current 1<br>`pm_i3_pv_current_1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x022C` (556) — PM I3 PV Current 2<br>`pm_i3_pv_current_2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x022D` (557) — PM I3 Battery Power Charge<br>`pm_i3_battery_power_charge` | Input (3x) | FC04 read | int16 |
| `0x022E` (558) — PM I3 Battery Voltage Charge<br>`pm_i3_battery_voltage_charge` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x022F` (559) — PM I3 Battery Current Charge<br>`pm_i3_battery_current_charge` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0233` (563) — PM I3 Battery Capacity<br>`pm_i3_battery_capacity_charge` | Input (3x) | FC04 read | uint16 |
