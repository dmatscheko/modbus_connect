# Husdata H60 — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/husdata-h60.yaml`

## Primary source

- **Husdata — H1 Interface Developer’s Manual (Common-register ID-code table)** (H1 manual fw 10.18 (© 2013–2014); H60 Modbus-TCP page retrieved 2026-07-11)
- Source: [https://husdata.se/wp-content/uploads/2015/11/H1-Manual-10.184.pdf](https://husdata.se/wp-content/uploads/2015/11/H1-Manual-10.184.pdf)
- Also: [https://husdata.se/docs/h60-manual/modbus-tcp-integrations/](https://husdata.se/docs/h60-manual/modbus-tcp-integrations/)
- Source type: official-manufacturer (husdata.se / Arandis AB)
- Register addresses vs device file: partial — the Common-register ID-code table matches the device file’s sensors (0001 Radiator return … 0009 Hot water; 0107/0111 setpoints) and its int16 ×0.1 scaling (type-0 ‘divide by 10’, two’s-complement); but the exact Modbus offsets (0,1,…,9,27) are assigned per heat-pump by H60 firmware, not enumerated in a static document
- Local copy: [`H1-Manual-10.184.pdf`](./H1-Manual-10.184.pdf) — 94 KB — primary source
- Local copy: [`H60-Modbus-TCP-Integrations.html`](./H60-Modbus-TCP-Integrations.html) — 106 KB

> The H1 developer’s manual is the register/ID-code reference the whole H-series (incl. H60) shares. Husdata exposes readable params as input registers (FC04, read-only) and writable ones as holding — matching this device file. The concrete address↔sensor mapping is shown per heat-pump model in the H60 web UI’s ‘Modbus’ column, so it varies by pump/firmware.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 9 (Input 9)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x0000` (0) — Water feed out to underfloor<br>`UnderfloorForward` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0001` (1) — HP Internal heat carrier return<br>`HeatCarrierReturn` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0002` (2) — HP internal heat supply forward<br>`HeatCarrierForward` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0003` (3) — From ground loops<br>`BrineIn` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0004` (4) — To ground loops<br>`BrineOut` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0005` (5) — Outdoor Temperature<br>`Outdoor` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0006` (6) — Indoor Temperature<br>`Indoor` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0009` (9) — DHW Actual Temperature<br>`HotWaterActual` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x001B` (27) — DHW Target Temperature<br>`HotWaterTarget` | Input (3x) | FC04 read | uint16 · ×0.1 |
