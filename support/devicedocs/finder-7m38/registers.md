# Finder 7M.38 — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/7M_38.yaml`

## Primary source

- **Finder — MODBUS Communication Protocol 7M.24 / 7M.38** (v2, 2021-06-30)
- Source: [https://cdn.findernet.com/app/uploads/2021/09/20090052/Modbus-7M24-7M38_v2_30062021.pdf](https://cdn.findernet.com/app/uploads/2021/09/20090052/Modbus-7M24-7M38_v2_30062021.pdf)
- Source type: official-manufacturer (Finder CDN, cdn.findernet.com)
- Register addresses vs device file: verified — per-phase + totals IEEE-754 float bank (FC04, base 30000, HI-word first): U1 32500, P1 32530, Pt 32536…; energy counters 30462–30485 (uint32, ×0.1)
- Local copy: [`Modbus-7M24-7M38_v2_30062021.pdf`](./Modbus-7M24-7M38_v2_30062021.pdf) — 742 KB

> One combined Finder document covers 7M.24, 7M.38 (and 7M.40). Input registers only, FC04, reference base 30000, IEEE-754 big-endian (HI word at the lower address).

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 35 (Input 35)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x09C4` (2500) — L1 Voltage | Input (3x) | FC04 read | float32 |
| `0x09C6` (2502) — L2 Voltage | Input (3x) | FC04 read | float32 |
| `0x09C8` (2504) — L3 Voltage | Input (3x) | FC04 read | float32 |
| `0x09D4` (2516) — L1 Current | Input (3x) | FC04 read | float32 |
| `0x09D6` (2518) — L2 Current | Input (3x) | FC04 read | float32 |
| `0x09D8` (2520) — L3 Current | Input (3x) | FC04 read | float32 |
| `0x09E2` (2530) — L1 active Power | Input (3x) | FC04 read | float32 |
| `0x09E4` (2532) — L2 active Power | Input (3x) | FC04 read | float32 |
| `0x09E6` (2534) — L3 active Power | Input (3x) | FC04 read | float32 |
| `0x09E8` (2536) — Total active Power | Input (3x) | FC04 read | float32 |
| `0x09F2` (2546) — L1 apparent Power | Input (3x) | FC04 read | float32 |
| `0x09F4` (2548) — L2 apparent Power | Input (3x) | FC04 read | float32 |
| `0x09F6` (2550) — L3 apparent Power | Input (3x) | FC04 read | float32 |
| `0x09F8` (2552) — Total apparent Power | Input (3x) | FC04 read | float32 |
| `0x09EA` (2538) — L1 reactive Power | Input (3x) | FC04 read | float32 |
| `0x09EC` (2540) — L2 reactive Power | Input (3x) | FC04 read | float32 |
| `0x09EE` (2542) — L3 reactive Power | Input (3x) | FC04 read | float32 |
| `0x09F0` (2544) — Total reactive Power | Input (3x) | FC04 read | float32 |
| `0x09C2` (2498) — Frequency | Input (3x) | FC04 read | float32 |
| `0x09FA` (2554) — L1 Power Factor | Input (3x) | FC04 read | float32 |
| `0x09FC` (2556) — L2 Power Factor | Input (3x) | FC04 read | float32 |
| `0x09FE` (2558) — L3 Power Factor | Input (3x) | FC04 read | float32 |
| `0x0A00` (2560) — Total Power Factor | Input (3x) | FC04 read | float32 |
| `0x01CE` (462) — Counter N1 | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x01D0` (464) — Counter N2 | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x01D2` (466) — Counter N3 | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x01D4` (468) — Counter N4 | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x01D6` (470) — Counter C1 | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x01D8` (472) — Counter C2 | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x01DA` (474) — Counter C3 | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x01DC` (476) — Counter C4 | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x01DE` (478) — Counter C5 | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x01E0` (480) — Counter C6 | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x01E2` (482) — Counter C7 | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x01E4` (484) — Counter C8 | Input (3x) | FC04 read | uint32 · ×0.1 |
