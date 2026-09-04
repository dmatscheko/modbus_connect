# Anhui QDF70B Pressure Sensor — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/anhui-qdf70b-pressure-sensor.yaml`

## Primary source

- **Anhui Qidian — MODBUS Pressure and Level transmitter communication protocol** (PDF authored 2024-12-10, listed as 'Pressure level sensor' (2024-12-26) on the RS485-Modbus-RTU manual page)
- Source: [http://www.qidian-zdk.com/rs485-modbus-rtu](http://www.qidian-zdk.com/rs485-modbus-rtu)
- Also: [http://www.qidian-zdk.com/pressure-measurement-series](http://www.qidian-zdk.com/pressure-measurement-series)
- Also: [https://s2ins.com/wp-content/uploads/2024/11/Pressure-Sensor-Transmitter-QDW90A-O4-0-500Bar-Output-RS485.pdf](https://s2ins.com/wp-content/uploads/2024/11/Pressure-Sensor-Transmitter-QDW90A-O4-0-500Bar-Output-RS485.pdf)
- Source type: official-manufacturer (Anhui Qidian Automation Technology, qidian-zdk.com manual download; the family-wide protocol for the QDF70B / QDW90A / QDY transmitters)
- Register addresses vs device file: verified — 0-based PDU addresses (the document's example frame 01 03 00 04 00 01 reads the value): 0x0004 measured value (int16, scaled by the 0x0003 decimal-places register, unit per 0x0002), 0x0016–0x0017 float32 big-endian copy; setup 0x0000 address, 0x0001 baud, 0x0025 parity, 0x000C zero offset, 0x0005/0x0006 range points, 0x000F save, 0x0010 factory restore. Holding register 9 answers on the hardware but is absent from the document
- Local copy: [`qidian-pressure-level-sensor-modbus-rtu-protocol.pdf`](./qidian-pressure-level-sensor-modbus-rtu-protocol.pdf) — 111 KB

> The site's download list serves the PDF through a JavaScript download API (no static link); the identical file (same checksum) is mirrored by the s2ins.com distributor. The document is the generic protocol of the whole pressure/level transmitter family and does not name the QDF70B; the unit and decimal-places registers decide how the integer value is scaled — the device file assumes Pa with 0 decimals (see caveats.md).

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 13 (Holding 13)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x0004` (4) — Pressure<br>`pressure` | Holding (4x) | FC03 read | int16 |
| `0x0016` (22) — Pressure (float)<br>`pressure_float` | Holding (4x) | FC03 read | float32 |
| `0x0002` (2) — Pressure unit<br>`pressure_unit` | Holding (4x) | FC03 read | uint16 · enum · 24 opts |
| `0x0003` (3) — Decimal places<br>`decimal_places` | Holding (4x) | FC03 read | uint16 |
| `0x0005` (5) — Range zero point<br>`range_zero_point` | Holding (4x) | FC03 read | int16 |
| `0x0006` (6) — Range full point<br>`range_full_point` | Holding (4x) | FC03 read | int16 |
| `0x000C` (12) — Zero offset<br>`zero_offset` | Holding (4x) | FC03 read · FC06 write | int16 |
| `0x0009` (9) — Undocumented register 9<br>`undocumented_register_9` | Holding (4x) | FC03 read | int16 |
| `0x0000` (0) — Modbus address<br>`modbus_address` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0001` (1) — Modbus baud rate<br>`baud_rate` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 8 opts |
| `0x0025` (37) — Modbus parity<br>`parity` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x000F` (15) — Save settings<br>`save_settings` | Holding (4x) | FC06 write-only | uint16 |
| `0x0010` (16) — Restore factory settings<br>`restore_factory_settings` | Holding (4x) | FC06 write-only | uint16 |
