# SolaX Power X3-HAC (11 kW) — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/Solax_X3_HAC.yaml`

## Primary source

- **SolaX — X1/X3-HAC EV Charger Modbus RTU/TCP Communication Protocol** (V1.0.0 EN)
- Source: [https://github.com/user-attachments/files/18746087/X1.X3-HAC.EV.Charger.Modbus.TCP.RTU.V1.0.0-EN.pdf](https://github.com/user-attachments/files/18746087/X1.X3-HAC.EV.Charger.Modbus.TCP.RTU.V1.0.0-EN.pdf)
- Source type: manufacturer-authored PDF, community-hosted (SolaX does not publish it publicly)
- Register addresses vs device file: verified — holding 0x060E–0x0669 → device-file 1548–1641 (device-lock, charge-current, boost timers, EVSE mode), input 0x00–0x36; 0-based PDU
- Local copy: [`SolaX-X1X3-HAC-EV-Charger-ModbusTCP-RTU-V1.0.0-EN.pdf`](./SolaX-X1X3-HAC-EV-Charger-ModbusTCP-RTU-V1.0.0-EN.pdf) — 685 KB — primary source
- Local copy: [`caveats.md`](./caveats.md) — 730 bytes
- Local copy: [`groups.md`](./groups.md) — 1 KB

> Exact-model document (title page ‘X1/X3-HAC EV charger’); the power-rating enum includes 2 = 11 kW. SolaX does not publish publicly; genuine SolaX PDF redistributed via GitHub.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 84 (Holding 32, Input 52) · plus 1 composite template entities

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x060C` (1548) — Meter Setting<br>`meter_setting` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x060D` (1549) — Charger Use Mode<br>`charger_use_mode` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x060E` (1550) — ECO Gear<br>`eco_gear` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 5 opts |
| `0x060F` (1551) — Green Gear<br>`green_gear` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0610` (1552) — Start Charge Mode<br>`start_charge_mode` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x0611` (1553) — Overload Limit<br>`overload_limit` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0612` (1554) — Undervoltage Limit<br>`undervoltage_limit` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0613` (1555) — Boost Mode<br>`boost_mode` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x0614` (1556) — Main Breaker Limit<br>`main_breaker_limit` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0615` (1557) — Device Lock<br>`device_lock` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0616` (1558) — RFID Card Activation<br>`rfid_program` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0619` (1561) — Charge Added Total<br>`charge_added_total` | Holding (4x) | FC03 read | uint32 · swap word · ×0.1 |
| `0x061C` (1564) — Charging Mode<br>`evse_scene` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x061D` (1565) — Sync RTC<br>`sync_rtc` | Holding (4x) | FC16 write-only | uint16 |
| `0x061D` (1565) — rtc_tz _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x061E` (1566) — rtc_second _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x061F` (1567) — rtc_minute _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0620` (1568) — rtc_hour _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0621` (1569) — rtc_day _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0622` (1570) — rtc_month _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0623` (1571) — rtc_year _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x0625` (1573) — Charge Phase<br>`charge_phase` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x0627` (1575) — Control Command<br>`control_command` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 7 opts |
| `0x0628` (1576) — Charge Current<br>`charge_current` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.01 |
| `0x0634` (1588) — Timer Boost Start Time<br>`timer_boost_start_time` | Holding (4x) | FC03 read · FC16 write | time hh:mm · 2 regs |
| `0x0636` (1590) — Timer Boost End Time<br>`timer_boost_end_time` | Holding (4x) | FC03 read · FC16 write | time hh:mm · 2 regs |
| `0x0638` (1592) — Smart Boost End Time<br>`smart_boost_end_time` | Holding (4x) | FC03 read · FC16 write | time hh:mm · 2 regs |
| `0x063A` (1594) — Smart Boost Energy<br>`smart_boost_energy` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x063B` (1595) — Charge Phase Alt<br>`charge_phase_alt` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x0640` (1600) — Modbus Address<br>`modbus_address` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0668` (1640) — Max Charge Current<br>`max_charge_current` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.01 |
| `0x0669` (1641) — EVSE Mode<br>`evse_mode` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x0000` (0) — Charge Voltage L1<br>`charge_voltage_l1` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0001` (1) — Charge Voltage L2<br>`charge_voltage_l2` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0002` (2) — Charge Voltage L3<br>`charge_voltage_l3` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0003` (3) — Charge PE Voltage<br>`charge_pe_voltage` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0004` (4) — Charge Current L1<br>`charge_current_l1` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0005` (5) — Charge Current L2<br>`charge_current_l2` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0006` (6) — Charge Current L3<br>`charge_current_l3` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0007` (7) — Charge PE Current<br>`charge_pe_current` | Input (3x) | FC04 read | uint16 |
| `0x0008` (8) — Charge Power L1<br>`charge_power_l1` | Input (3x) | FC04 read | uint16 |
| `0x0009` (9) — Charge Power L2<br>`charge_power_l2` | Input (3x) | FC04 read | uint16 |
| `0x000A` (10) — Charge Power L3<br>`charge_power_l3` | Input (3x) | FC04 read | uint16 |
| `0x000B` (11) — Charge Power Total<br>`charge_power_total` | Input (3x) | FC04 read | uint16 |
| `0x000C` (12) — Charge Frequency L1<br>`charge_frequency_l1` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x000D` (13) — Charge Frequency L2<br>`charge_frequency_l2` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x000E` (14) — Charge Frequency L3<br>`charge_frequency_l3` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x000F` (15) — Charge Added<br>`charge_added` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0010` (16) — Charge Added - Cumulative<br>`charge_added_cum` | Input (3x) | FC04 read | uint32 · swap word · ×0.1 |
| `0x0012` (18) — Grid Current L1<br>`grid_current_l1` | Input (3x) | FC04 read | int16 · ×0.01 |
| `0x0013` (19) — Grid Current L2<br>`grid_current_l2` | Input (3x) | FC04 read | int16 · ×0.01 |
| `0x0014` (20) — Grid Current L3<br>`grid_current_l3` | Input (3x) | FC04 read | int16 · ×0.01 |
| `0x0015` (21) — Grid Power L1<br>`grid_power_l1` | Input (3x) | FC04 read | int16 |
| `0x0016` (22) — Grid Power L2<br>`grid_power_l2` | Input (3x) | FC04 read | int16 |
| `0x0017` (23) — Grid Power L3<br>`grid_power_l3` | Input (3x) | FC04 read | int16 |
| `0x0018` (24) — Grid Power Total<br>`grid_power_total` | Input (3x) | FC04 read | int16 |
| `0x0019` (25) — CC Voltage<br>`cc_voltage` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x001A` (26) — CP Voltage<br>`cp_voltage` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x001B` (27) — PWM Duty Cycle<br>`pwm_duty_cycle` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x001C` (28) — Charger Temperature<br>`charger_temperature` | Input (3x) | FC04 read | uint16 |
| `0x001D` (29) — Run Mode<br>`run_mode` | Input (3x) | FC04 read | uint16 · enum · 14 opts |
| `0x001E` (30) — Fault Code<br>`fault_code` | Input (3x) | FC04 read | uint32 · swap word |
| `0x0020` (32) — Case Type<br>`case_type` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x0021` (33) — Power Rating<br>`power_rating` | Input (3x) | FC04 read | uint16 · enum · 4 opts |
| `0x0022` (34) — Phase Type<br>`phase_type` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x0023` (35) — Charging Scene<br>`model_type` | Input (3x) | FC04 read | uint16 · enum · 3 opts |
| `0x0024` (36) — Screen Fitted<br>`screen_fitted` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x0025` (37) — firmware_version _(internal)_ | Input (3x) | FC04 read | uint16 |
| `0x0027` (39) — RSSI<br>`rssi` | Input (3x) | FC04 read | uint16 |
| `0x0028` (40) — Active Charge Phase<br>`active_charge_phase` | Input (3x) | FC04 read | uint16 · enum · 4 opts |
| `0x0029` (41) — Unbalanced Power Limit<br>`unbalanced_power_limit` | Input (3x) | FC04 read | uint16 |
| `0x002A` (42) — Phase Unbalance<br>`phase_unbalance` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x002B` (43) — Charging Duration<br>`charge_duration` | Input (3x) | FC04 read | uint32 · swap word |
| `0x002D` (45) — Lock State<br>`lock_state` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x002E` (46) — Main Breaker Limit State<br>`mainbrk_limit` | Input (3x) | FC04 read | uint16 · enum · 3 opts |
| `0x002F` (47) — Random Delay State<br>`delay_state` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x0030` (48) — Ban State<br>`ban_state` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x0100` (256) — Charge Power L1 Alt<br>`charge_power_l1_alt` | Input (3x) | FC04 read | uint16 |
| `0x0101` (257) — Charge Power L2 Alt<br>`charge_power_l2_alt` | Input (3x) | FC04 read | uint16 |
| `0x0102` (258) — Charge Power L3 Alt<br>`charge_power_l3_alt` | Input (3x) | FC04 read | uint16 |
| `0x0103` (259) — Max Power Charging<br>`max_power_charging` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
| `0x0104` (260) — Charge Mode Active<br>`charge_mode_active` | Input (3x) | FC04 read | uint16 · enum · 3 opts |
| `0x0105` (261) — Green Mode Start Power<br>`green_mode_start_power` | Input (3x) | FC04 read | uint16 |
| `0x0106` (262) — Run Mode Alt<br>`charger_status` | Input (3x) | FC04 read | uint16 · enum · 14 opts |
