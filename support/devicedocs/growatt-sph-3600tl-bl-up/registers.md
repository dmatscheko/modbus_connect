# Growatt SPH3600TL BL_UP — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/SPH-3600TL-BL_UP.yaml`

## Primary source

- **Growatt Inverter Modbus RTU Protocol (a.k.a. Protocol II)** (V1.24 (first release 2020-04-28))
- Source: [https://github.com/johanmeijer/grott/blob/master/documentatie/Growatt-Inverter-Modbus-RTU-Protocol-II-V1-24-English-new.pdf](https://github.com/johanmeijer/grott/blob/master/documentatie/Growatt-Inverter-Modbus-RTU-Protocol-II-V1-24-English-new.pdf)
- Source type: manufacturer-authored PDF, community-hosted (grott mirror; Growatt does not publish it publicly)
- Register addresses vs device file: verified — SPH storage family: base 0–124 input (37 Fac, 38 Vac1, 40 Pac1 uint32, 93 Temp) + storage 1000–1124 (input 1009–1041 battery/SOC; holding 1044/1070/1090)
- Local copy: [`Growatt-Inverter-Modbus-RTU-Protocol-II-V1.24-English.pdf`](./Growatt-Inverter-Modbus-RTU-Protocol-II-V1.24-English.pdf) — 737 KB

> Growatt does not host the protocol PDF publicly; verbatim grott mirror. SPH storage config lives in the 1000-range holding (unlike the TL-XH 3000-range). Big-endian; FC03/FC04 read, FC06/FC16 write.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 31 (Holding 13, Input 18)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x0009` (9) — Firmware version<br>`hw_version` | Holding (4x) | FC03 read | string · 3 regs (6 chars) |
| `0x000C` (12) — Control firmware version<br>`sw_version` | Holding (4x) | FC03 read | string · 3 regs (6 chars) |
| `0x0017` (23) — Serial Number<br>`serial_no` | Holding (4x) | FC03 read | string · 5 regs (10 chars) |
| `0x0000` (0) — Remote On/Off<br>`on_off` | Holding (4x) | FC03 read · FC06 write | uint16 · on=1 |
| `0x000F` (15) — LCD language<br>`language` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 9 opts |
| `0x0016` (22) — Baud Rate<br>`baud_rate` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x0424` (1060) — UPS On/Off<br>`ups_on_off` | Holding (4x) | FC03 read · FC06 write | uint16 · on=1 |
| `0x0414` (1044) — Priority Mode<br>`priority_mode` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x0426` (1062) — UPS Output Voltage<br>`ups_output_voltage` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x042E` (1070) — Discharge Power Rate (Grid First)<br>`discharge_power_rate` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x042F` (1071) — Discharge Stop SoC (Grid First)<br>`discharge_stop_soc` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0442` (1090) — Charge Stop SoC (Battery First)<br>`charge_stop_soc` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0444` (1092) — AC Charge<br>`ac_charge` | Holding (4x) | FC03 read · FC06 write | uint16 · on=1 |
| `0x0000` (0) — Inverter Status<br>`machine_status` | Input (3x) | FC04 read | uint16 · enum · 3 opts |
| `0x0025` (37) — Grid frequency<br>`Fac` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0026` (38) — Grid voltage<br>`Vac1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0027` (39) — Grid output current<br>`Iac1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0028` (40) — Grid output watt VA<br>`Pac1` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x005D` (93) — Inverter temperature<br>`Temp1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x005E` (94) — IPM Inverter temperature<br>`Temp2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x005F` (95) — Boost temperature<br>`Temp3` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0074` (116) — Charge Power<br>`ac_charge_power` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x03E8` (1000) — System Work Mode<br>`work_mode` | Input (3x) | FC04 read | uint16 · mask 0xFF00 · enum · 8 opts |
| `0x03F1` (1009) — Discharge power<br>`pdischr` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x03F5` (1013) — Battery voltage<br>`vbat` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x03F6` (1014) — SoC<br>`soc` | Input (3x) | FC04 read | uint16 |
| `0x03F7` (1015) — AC power to user<br>`Pactouser` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0407` (1031) — Inverter power to local load<br>`PLocalLoad` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x040D` (1037) — Inverter power to local load total<br>`PLocalLoad_total` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0410` (1040) — Battery temperature<br>`BattTemp` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0411` (1041) — SPS DSP Status<br>`sps_dsp_status` | Input (3x) | FC04 read | uint16 · enum · 2 opts |
