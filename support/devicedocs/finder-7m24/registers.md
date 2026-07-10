# Finder 7M.24 — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/7M_24.yaml`

## Primary source

- **Finder — MODBUS Communication Protocol 7M.24 / 7M.38** (v2, 2021-06-30)
- Source: [https://cdn.findernet.com/app/uploads/2021/09/20090052/Modbus-7M24-7M38_v2_30062021.pdf](https://cdn.findernet.com/app/uploads/2021/09/20090052/Modbus-7M24-7M38_v2_30062021.pdf)
- Source type: official-manufacturer (Finder CDN, cdn.findernet.com)
- Register addresses vs device file: verified — IEEE-754 float bank (FC04, reference base 30000, big-endian HI-word first): Freq 32498, U1 32500, I1 32516, P1 32530…; energy counters 30462–30485 (uint32)
- Local copy: [`Modbus-7M24-7M38_v2_30062021.pdf`](./Modbus-7M24-7M38_v2_30062021.pdf) — 742 KB

> One combined Finder document covers 7M.24, 7M.38 (and 7M.40). The document specifies ×0.1 (‘x 0,1 Wh’) on the energy counters (30462–30485); both device files apply that multiplier.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 19 (Input 19)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x09C4` (2500) — Voltage | Input (3x) | FC04 read | float32 |
| `0x09D4` (2516) — Current | Input (3x) | FC04 read | float32 |
| `0x09E2` (2530) — Active Power | Input (3x) | FC04 read | float32 |
| `0x09F2` (2546) — Apparent Power | Input (3x) | FC04 read | float32 |
| `0x09EA` (2538) — Reactive Power | Input (3x) | FC04 read | float32 |
| `0x09C2` (2498) — Frequency | Input (3x) | FC04 read | float32 |
| `0x09FA` (2554) — Power Factor | Input (3x) | FC04 read | float32 |
| `0x01CE` (462) — Counter N1 | Input (3x) | FC04 read | uint32 |
| `0x01D0` (464) — Counter N2 | Input (3x) | FC04 read | uint32 |
| `0x01D2` (466) — Counter N3 | Input (3x) | FC04 read | uint32 |
| `0x01D4` (468) — Counter N4 | Input (3x) | FC04 read | uint32 |
| `0x01D6` (470) — Counter C1 | Input (3x) | FC04 read | uint32 |
| `0x01D8` (472) — Counter C2 | Input (3x) | FC04 read | uint32 |
| `0x01DA` (474) — Counter C3 | Input (3x) | FC04 read | uint32 |
| `0x01DC` (476) — Counter C4 | Input (3x) | FC04 read | uint32 |
| `0x01DE` (478) — Counter C5 | Input (3x) | FC04 read | uint32 |
| `0x01E0` (480) — Counter C6 | Input (3x) | FC04 read | uint32 |
| `0x01E2` (482) — Counter C7 | Input (3x) | FC04 read | uint32 |
| `0x01E4` (484) — Counter C8 | Input (3x) | FC04 read | uint32 |
