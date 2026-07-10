# Eastron SDM-230 — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/SDM230.yaml`

## Primary source

- **Eastron SDM230-Modbus — Modbus Protocol Implementation** (Eastron Europe (undated) + eastron.com.cn V1.2 + user manual V1.8)
- Source: [https://downloads.innon.com/hubfs/downloads.innon.com/Power%20Meters/SDM230-MOD-MID/Manuals/SDM230-PROTOCOL.pdf](https://downloads.innon.com/hubfs/downloads.innon.com/Power%20Meters/SDM230-MOD-MID/Manuals/SDM230-PROTOCOL.pdf)
- Source type: official-manufacturer (Eastron-authored; protocol PDFs are login-gated on eastron.* so the protocol copy is from a distributor mirror)
- Register addresses vs device file: verified — measurements = input float32 pairs from 0x0000 (FC04, MSB-register first); config = holding (FC03 read / FC16 write): Node 0x14, Baud 0x1C, energy 0x48–0x4E
- Local copy: [`eastroneurope-SDM230-Protocol.pdf`](./eastroneurope-SDM230-Protocol.pdf) — 527 KB — primary source
- Local copy: [`eastron-sdm230-modbus-usermanual-v1.8.pdf`](./eastron-sdm230-modbus-usermanual-v1.8.pdf) — 1.2 MB
- Local copy: [`eastron-SDM230Modbus-Protocol-V1.2.pdf`](./eastron-SDM230Modbus-Protocol-V1.2.pdf) — 508 KB

> Eastron gates protocol PDFs behind login on its own sites, so the protocol copy is the genuine Eastron-branded doc mirrored by the Innon distributor; the official eastrongroup.com user manual (V1.8) is also included. Note: the device-file baud map (…5=1200 bps) matches the older eastron.com.cn V1.2 protocol; the newer Europe revision lists 3=19200/4=38400 instead — both protocol PDFs are in this folder.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 25 (Holding 3, Input 22)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0xFC00` (64512) — Serial Number<br>`serial_num` | Holding (4x) | FC03 read | uint32 |
| `0x0014` (20) — Communicate address<br>`com_address` | Holding (4x) | FC03 read · FC16 write | float32 |
| `0x001C` (28) — Baud Rate<br>`baud_rate` | Holding (4x) | FC03 read · FC16 write | float32 · enum · 4 opts |
| `0x0054` (84) — Total system power demand | Input (3x) | FC04 read | float32 |
| `0x0056` (86) — Maximum total system power demand | Input (3x) | FC04 read | float32 |
| `0x0058` (88) — Current system import power demand | Input (3x) | FC04 read | float32 |
| `0x005A` (90) — Maximum system import power demand | Input (3x) | FC04 read | float32 |
| `0x005C` (92) — Current system export power demand | Input (3x) | FC04 read | float32 |
| `0x005E` (94) — Maximum system export power demand | Input (3x) | FC04 read | float32 |
| `0x0000` (0) — Voltage | Input (3x) | FC04 read | float32 |
| `0x0006` (6) — Current | Input (3x) | FC04 read | float32 |
| `0x000C` (12) — Active Power | Input (3x) | FC04 read | float32 |
| `0x0012` (18) — Apparent Power | Input (3x) | FC04 read | float32 |
| `0x0018` (24) — Reactive Power | Input (3x) | FC04 read | float32 |
| `0x001E` (30) — Power Factor | Input (3x) | FC04 read | float32 |
| `0x0024` (36) — Phase Angle | Input (3x) | FC04 read | float32 |
| `0x0046` (70) — Frequency | Input (3x) | FC04 read | float32 |
| `0x0048` (72) — Import Active Energy | Input (3x) | FC04 read | float32 |
| `0x004A` (74) — Export Active Energy | Input (3x) | FC04 read | float32 |
| `0x004C` (76) — Import Reactive Energy | Input (3x) | FC04 read | float32 |
| `0x004E` (78) — Export Reactive Energy | Input (3x) | FC04 read | float32 |
| `0x0102` (258) — Current demand | Input (3x) | FC04 read | float32 |
| `0x0108` (264) — Maximum current Demand | Input (3x) | FC04 read | float32 |
| `0x0156` (342) — Total Active Energy | Input (3x) | FC04 read | float32 |
| `0x0158` (344) — Total Reactive Energy | Input (3x) | FC04 read | float32 |
