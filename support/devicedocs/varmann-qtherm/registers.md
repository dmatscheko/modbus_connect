# Varmann Qtherm — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/Varmann Qtherm.yaml`

## Primary source

- **VARMANN — Exchange Protocol with convector control units** (unversioned (firmware ≥ 1013; PDF metadata 2016–2019))
- Source: [https://www.varmann.ru/download/downloads_files/Exchange_Protocol_with_VARMANN_convector_control_units.pdf](https://www.varmann.ru/download/downloads_files/Exchange_Protocol_with_VARMANN_convector_control_units.pdf)
- Source type: official-manufacturer (varmann.ru; Russian-language)
- Register addresses vs device file: verified — holding 0x00–0x17 map one-for-one (0x02 UstTmp ×10, 0x06 UstFan %, 0x13 I_Manual bit flags, 0x09 TmpOut ×10); FC03 read, FC06 write-single, FC16 write-multiple; default slave 16
- Local copy: [`Exchange_Protocol_with_VARMANN_convector_control_units.pdf`](./Exchange_Protocol_with_VARMANN_convector_control_units.pdf) — 123 KB

> The manufacturer document is Russian-language (VARMANN is a Russian brand). Note: the doc defines register 0x03 HeatChill as 1=heat / 2=cool / 3=heat+cool, whereas the device file maps 0=Heating / 1=Cooling / 2=Auto (shifted by −1).

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 24 (Holding 24)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x0000` (0) — Slave Address<br>`slave_address` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0001` (1) — Temperature NTC<br>`tmp_ntc` | Holding (4x) | FC03 read | uint16 · ×0.1 |
| `0x0002` (2) — Required Temperature<br>`ust_tmp` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x0003` (3) — Heat/Chill Mode<br>`heat_chill` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x0004` (4) — Integration time<br>`timereg` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0005` (5) — Regulation profile<br>`kreg` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0006` (6) — Required Fan speed<br>`ust_fan` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0007` (7) — Heating valve<br>`valve_heat` | Holding (4x) | FC03 read · FC06 write | uint16 · on=1 |
| `0x0008` (8) — Cooling valve<br>`valve_chill` | Holding (4x) | FC03 read · FC06 write | uint16 · on=1 |
| `0x0009` (9) — Incoming temperature<br>`tmp_out` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x000A` (10) — LAN communication timeout<br>`time_lan` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x000B` (11) — ADC value<br>`vadc` | Holding (4x) | FC03 read | uint16 |
| `0x000C` (12) — Fan speed<br>`fan_ust` | Holding (4x) | FC03 read | uint16 |
| `0x000D` (13) — Heating valve state<br>`o_heat` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x000E` (14) — Cooling valve state<br>`o_chill` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x000F` (15) — Alarm status<br>`alarm` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0010` (16) — DIP Switch 1<br>`dip_1` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0011` (17) — DIP Switch 2<br>`dip_2` | Holding (4x) | FC03 read | uint16 · enum · 2 opts |
| `0x0012` (18) — Operating mode<br>`i_mode` | Holding (4x) | FC03 read | uint16 · on=1 |
| `0x0013` (19) — Manual control<br>`i_manual` | Holding (4x) | FC03 read | uint16 · mask 0x7 · bitfield · 3 flags |
| `0x0014` (20) — Motor drive frequency<br>`freq_sin` | Holding (4x) | FC03 read | uint16 |
| `0x0015` (21) — Motor drive amplitude<br>`amp_sin` | Holding (4x) | FC03 read | uint16 |
| `0x0016` (22) — Motor current<br>`ishunt` | Holding (4x) | FC03 read | uint16 |
| `0x0017` (23) — Motor nominal current<br>`inorm` | Holding (4x) | FC03 read · FC06 write | uint16 |
