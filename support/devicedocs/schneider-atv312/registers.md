# Schneider Electric Altivar ATV312 — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/Schneider_ATV312.yaml`

## Primary source

- **Schneider Electric — Altivar 312 Communication Variables Manual (BBV51701)** (V1, 06/2009)
- Source: [https://www.se.com/ww/en/download/document/BBV51701/](https://www.se.com/ww/en/download/document/BBV51701/)
- Source type: official-manufacturer (download.schneider-electric.com)
- Register addresses vs device file: verified — logical ‘W’ word addresses are used directly as Modbus addresses (8501 CMD, 8502 LFr, 8503 PISP, 6001 Add, 9001/9002 ACC/dEC); all appear in the manual’s address index
- Local copy: [`ATV312_communication_variables_EN_BBV51701.pdf`](./ATV312_communication_variables_EN_BBV51701.pdf) — 728 KB — primary source
- Local copy: [`ATV312_Modbus_communication_manual_EN_BBV52816.pdf`](./ATV312_Modbus_communication_manual_EN_BBV52816.pdf) — 442 KB

> BBV51701 is the register-list manual (control / monitoring / configuration variables + address index). The companion BBV52816 (Modbus communication manual — framing / wiring) is also in this folder. ATV312 uses FC03 read, FC06 write-single, FC16 write-multiple; no address offset.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 74 (Holding 74)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x2136` (8502) — LFr Frequency Reference via Bus<br>`lfr_frequency_reference_via_bus` | Holding (4x) | FC03 read · FC06 write | int16 · ×0.1 |
| `0x2135` (8501) — CMD Control Word<br>`cmd_control_word` | Holding (4x) | FC03 read | uint16 |
| `0x2137` (8503) — PISP PI Reference via Bus<br>`pisp_pi_reference_via_bus` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x2329` (9001) — ACC Acceleration Ramp Time<br>`acc_acceleration_ramp_time` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x232A` (9002) — dEC Deceleration Ramp Time<br>`dec_deceleration_ramp_time` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x0C21` (3105) — LSP Low Speed<br>`lsp_low_speed` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x0C20` (3104) — HSP High Speed<br>`hsp_high_speed` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x0C1F` (3103) — tFr Maximum Output Frequency<br>`tfr_maximum_output_frequency` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x2596` (9622) — ItH Motor Thermal Protection Current<br>`ith_motor_thermal_protection_current` | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x23F1` (9201) — CLI Current Limit<br>`cli_current_limit` | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x2AFB` (11003) — Ftd Motor Frequency Threshold<br>`ftd_motor_frequency_threshold` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x1389` (5001) — Relay R1 Assignment<br>`relay_r1_assignment` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 15 opts |
| `0x138A` (5002) — Relay R2 Assignment<br>`relay_r2_assignment` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 16 opts |
| `0x2C25` (11301) — JPF Skip Frequency<br>`jpf_skip_frequency` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x2C26` (11302) — JF2 Second Skip Frequency<br>`jf2_second_skip_frequency` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x2DB5` (11701) — tLS Low Speed Operating Time<br>`tLS_low_speed_operating_time` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x232C` (9004) — rPt Ramp Type<br>`rpt_ramp_type` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x233C` (9020) — Inr Ramp Increment<br>`inr_ramp_increment` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x2334` (9012) — AC2 Second Acceleration Ramp Time<br>`ac2_second_acceleration_ramp_time` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x2335` (9013) — dE2 Second Deceleration Ramp Time<br>`de2_second_deceleration_ramp_time` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x2333` (9011) — Frt Ramp Switching Threshold<br>`frt_ramp_switching_threshold` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x232B` (9003) — brA Deceleration Ramp Adaptation<br>`bra_deceleration_ramp_adaptation` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0C1E` (3102) — SFr Switching Frequency<br>`sfr_switching_frequency` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x0C23` (3107) — nrd Noise Reduction<br>`nrd_noise_reduction` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x238D` (9101) — SrF Speed Loop Filter Suppression<br>`srf_speed_loop_filter_suppression` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x20DD` (8413) — Fr1 Reference Channel 1<br>`fr1_reference_channel_1` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 9 opts |
| `0x20DE` (8414) — Fr2 Reference Channel 2<br>`fr2_reference_channel_2` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 10 opts |
| `0x20E7` (8423) — Cd1 Control Channel 1<br>`cd1_control_channel_1` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 5 opts |
| `0x20E8` (8424) — Cd2 Control Channel 2<br>`cd2_control_channel_2` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 5 opts |
| `0x0C81` (3201) — ETA Status Word<br>`eta_status_word` | Holding (4x) | FC03 read | uint16 · bitfield · 11 flags |
| `0x0C81` (3201) — Drive Fault Active<br>`drive_fault_active` | Holding (4x) | FC03 read | uint16 · mask 0x8 · on=1 |
| `0x0C81` (3201) — Drive Alarm Present<br>`drive_alarm_present` | Holding (4x) | FC03 read | uint16 · mask 0x80 · on=1 |
| `0x0C81` (3201) — Reference Reached<br>`reference_reached` | Holding (4x) | FC03 read | uint16 · mask 0x400 · on=1 |
| `0x0C82` (3202) — rFr Output Frequency<br>`rfr_output_frequency` | Holding (4x) | FC03 read | int16 · ×0.1 |
| `0x0C83` (3203) — FrH Frequency Reference Before Ramp<br>`frh_frequency_reference_before_ramp` | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x2149` (8521) — LFR1 Modbus Frequency Reference Image<br>`lfr1_modbus_frequency_reference_image` | Holding (4x) | FC03 read | int16 · ×0.1 |
| `0x0C84` (3204) — LCr Motor Current<br>`lcr_motor_current` | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x0C85` (3205) — Otr Motor Torque<br>`otr_motor_torque` | Holding (4x) | FC03 read | uint16 |
| `0x0C8B` (3211) — OPr Motor Power<br>`opr_motor_power` | Holding (4x) | FC03 read | uint16 |
| `0x0C87` (3207) — ULn Line Voltage<br>`uln_line_voltage` | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x259E` (9630) — tHr Motor Thermal State<br>`thr_motor_thermal_state` | Holding (4x) | FC03 read | uint16 |
| `0x0C89` (3209) — tHd Drive Thermal State<br>`thd_drive_thermal_state` | Holding (4x) | FC03 read | uint16 |
| `0x0C8A` (3210) — TDM Max Drive Thermal State<br>`tdm_max_drive_thermal_state` | Holding (4x) | FC03 read | uint16 |
| `0x0C9F` (3231) — rtH Operating Time<br>`rth_operating_time` | Holding (4x) | FC03 read | uint16 |
| `0x0BC9` (3017) — INV Nominal Drive Current<br>`inv_nominal_drive_current` | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x0BC3` (3011) — NCV Drive Rating<br>`ncv_drive_rating` | Holding (4x) | FC03 read | uint16 · enum · 14 opts |
| `0x0BC4` (3012) — VCAL Drive Voltage<br>`vcal_drive_voltage_class` | Holding (4x) | FC03 read | uint16 · enum · 5 opts |
| `0x0CE6` (3302) — UdP Firmware Version Raw<br>`udp_firmware_version_raw` | Holding (4x) | FC03 read | uint16 |
| `0x0D49` (3401) — TSP Drive Firmware Type<br>`tsp_drive_firmware_type` | Holding (4x) | FC03 read | uint16 · enum · 1 opts |
| `0x0E11` (3601) — O1Ct Option Board 1 Type<br>`o1ct_option_board_1_type` | Holding (4x) | FC03 read | uint16 · enum · 3 opts |
| `0x1478` (5240) — Relay R1 Output Active<br>`relay_r1_output_active` | Holding (4x) | FC03 read | uint16 · mask 0x100 · on=1 |
| `0x1478` (5240) — Relay R2 Output Active<br>`relay_r2_output_active` | Holding (4x) | FC03 read | uint16 · mask 0x200 · on=1 |
| `0x1478` (5240) — Logic Output Active<br>`logic_output_active` | Holding (4x) | FC03 read | uint16 · mask 0x400 · on=1 |
| `0x1478` (5240) — IOLR Logic IO State<br>`iolr_logic_io_state` | Holding (4x) | FC03 read | uint16 · bitfield · 11 flags |
| `0x0C86` (3206) — Motor Running<br>`motor_running` | Holding (4x) | FC03 read | uint16 · mask 0x10 · on=1 |
| `0x0C86` (3206) — Drive Accelerating<br>`drive_accelerating` | Holding (4x) | FC03 read | uint16 · mask 0x200 · on=1 |
| `0x0C86` (3206) — Drive Decelerating<br>`drive_decelerating` | Holding (4x) | FC03 read | uint16 · mask 0x400 · on=1 |
| `0x0C86` (3206) — Current Limit Alarm<br>`current_limit_alarm` | Holding (4x) | FC03 read | uint16 · mask 0x800 · on=1 |
| `0x0C86` (3206) — ETI Extended Status Word<br>`eti_extended_status_word` | Holding (4x) | FC03 read | uint16 · bitfield · 12 flags |
| `0x0CB2` (3250) — Frequency Threshold Reached<br>`frequency_threshold_reached` | Holding (4x) | FC03 read | uint16 · mask 0x10 · on=1 |
| `0x0CB2` (3250) — High Speed Reached<br>`high_speed_reached` | Holding (4x) | FC03 read | uint16 · mask 0x20 · on=1 |
| `0x0CB2` (3250) — Speed Reference Reached Status<br>`speed_reference_reached_status` | Holding (4x) | FC03 read | uint16 · mask 0x80 · on=1 |
| `0x0CB2` (3250) — LRS1 Extended Status<br>`lrs1_extended_status` | Holding (4x) | FC03 read | uint16 · bitfield · 10 flags |
| `0x0CB4` (3252) — LRS3 Channel Status<br>`lrs3_channel_status` | Holding (4x) | FC03 read | uint16 · bitfield · 6 flags |
| `0x219E` (8606) — ERRD Active Fault Code<br>`errd_active_fault_code` | Holding (4x) | FC03 read | uint16 · enum · 21 opts |
| `0x1BD1` (7121) — LFt Last Detected Fault<br>`lft_last_detected_fault` | Holding (4x) | FC03 read | uint16 · enum · 32 opts |
| `0x1C21` (7201) — DP1 Past Detected Fault 1<br>`dp1_past_detected_fault_1` | Holding (4x) | FC03 read | uint16 · enum · 32 opts |
| `0x1C22` (7202) — DP2 Past Detected Fault 2<br>`dp2_past_detected_fault_2` | Holding (4x) | FC03 read | uint16 · enum · 32 opts |
| `0x1C23` (7203) — DP3 Past Detected Fault 3<br>`dp3_past_detected_fault_3` | Holding (4x) | FC03 read | uint16 · enum · 32 opts |
| `0x1C24` (7204) — DP4 Past Detected Fault 4<br>`dp4_past_detected_fault_4` | Holding (4x) | FC03 read | uint16 · enum · 32 opts |
| `0x1C2B` (7211) — EP1 Past Fault Status 1<br>`ep1_past_fault_status_1` | Holding (4x) | FC03 read | uint16 · bitfield · 11 flags |
| `0x1C2C` (7212) — EP2 Past Fault Status 2<br>`ep2_past_fault_status_2` | Holding (4x) | FC03 read | uint16 · bitfield · 11 flags |
| `0x1C2D` (7213) — EP3 Past Fault Status 3<br>`ep3_past_fault_status_3` | Holding (4x) | FC03 read | uint16 · bitfield · 11 flags |
| `0x1C2E` (7214) — EP4 Past Fault Status 4<br>`ep4_past_fault_status_4` | Holding (4x) | FC03 read | uint16 · bitfield · 11 flags |
