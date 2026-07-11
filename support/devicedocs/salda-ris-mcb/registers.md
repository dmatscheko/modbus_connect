# Salda RIS / RIRS (MCB) — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/Salda_RIS_MCB.yaml`

## Primary source

- **Salda — MCB Modbus register table (v1.29) + MCB / mini-MCB manual** (register table v1.29 (2026-04-22); manual v2019.1)
- Source: [http://salda.lt/mcb/downloads/doc/MCB%201.29%20Modbus%20table%202026-04-22.xlsx](http://salda.lt/mcb/downloads/doc/MCB%201.29%20Modbus%20table%202026-04-22.xlsx)
- Source type: official-manufacturer (salda.lt MCB config server)
- Register addresses vs device file: partial — holding regs match (fan-mode addr 1, setpoint addr 2) and the ‘Modbus PDU = XLS − 1’ (1-based XLS) note is confirmed; but the 4 temperature input addresses (0/3/6/9) do not match the table’s T1–T4 (18–21)
- Local copy: [`MCB 1.29 Modbus table 2026-04-22.xlsx`](./MCB%201.29%20Modbus%20table%202026-04-22.xlsx) — 89 KB — primary source
- Local copy: [`caveats.md`](./caveats.md) — 810 bytes
- Local copy: [`MCB_miniMCB [EN][SL] v2019.1.pdf`](./MCB_miniMCB%20[EN][SL]%20v2019.1.pdf) — 29.7 MB

> The .xlsx is the register table the device-file comment refers to (sheets: Holding / Coils / Discrete inputs / Input register / System state / Alarm list). The device file already notes its live temperatures use a custom layout, not the documented T1–T4. A ~30 MB MCB / mini-MCB installation manual PDF is also included in this folder.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 9 (Holding 3, Input 6) · plus 2 composite template entities

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x0000` (0) — Fan Speed<br>`fan_speed_select` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x0001` (1) — Temperature Set Point<br>`temperature_setpoint_number` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0000` (0) — fan_speed_raw _(internal)_ | Holding (4x) | FC03 read | uint16 |
| `0x000E` (14) — Current Mode<br>`current_system_mode` | Input (3x) | FC04 read | uint16 · enum · 5 opts |
| `0x000F` (15) — Current Air Flow Mode<br>`current_air_flow` | Input (3x) | FC04 read | uint16 |
| `0x0009` (9) — Outside Temperature<br>`outside_temperature` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0006` (6) — Inside Temperature<br>`inside_temperature` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0003` (3) — Supply Air Temperature<br>`supply_air_temperature` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0000` (0) — Exhaust Air Temperature<br>`exhaust_air_temperature` | Input (3x) | FC04 read | int16 · ×0.1 |
