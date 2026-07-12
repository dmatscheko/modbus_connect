# Waveshare Modbus RTU Relay (D) — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/waveshare-modbus-rtu-relay-d.yaml`

## Primary source

- **Waveshare Wiki — Modbus RTU Relay (D)** (living wiki page (retrieved 2026-07-11))
- Source: [https://www.waveshare.com/wiki/Modbus_RTU_Relay_(D)](https://www.waveshare.com/wiki/Modbus_RTU_Relay_(D))
- Source type: official-manufacturer (Waveshare product wiki)
- Register addresses vs device file: verified — relays = coils 0x0000–0x0007 (FC01/FC05); digital inputs = discrete inputs 0x0000–0x0007 (FC02); software version = holding 0x8000 (÷100)
- Local copy: [`wiki.html`](./wiki.html) — 99 KB

> The (D) variant adds 8 opto-isolated digital inputs, exposed as discrete inputs. Full protocol documented inline on the wiki (no separate PDF).

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 17 (Holding 1, Coil 8, Discrete 8)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x8000` (32768) — Software Version<br>`sw_version` | Holding (4x) | FC03 read | uint16 · ×0.01 |
| `0x0000` (0) — Relay 1<br>`relay_1` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0001` (1) — Relay 2<br>`relay_2` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0002` (2) — Relay 3<br>`relay_3` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0003` (3) — Relay 4<br>`relay_4` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0004` (4) — Relay 5<br>`relay_5` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0005` (5) — Relay 6<br>`relay_6` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0006` (6) — Relay 7<br>`relay_7` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0007` (7) — Relay 8<br>`relay_8` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0000` (0) — Relay 1 Status<br>`relay_1_status` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0001` (1) — Relay 2 Status<br>`relay_2_status` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0002` (2) — Relay 3 Status<br>`relay_3_status` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0003` (3) — Relay 4 Status<br>`relay_4_status` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0004` (4) — Relay 5 Status<br>`relay_5_status` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0005` (5) — Relay 6 Status<br>`relay_6_status` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0006` (6) — Relay 7 Status<br>`relay_7_status` | Discrete (1x) | FC02 read | bool (bit) |
| `0x0007` (7) — Relay 8 Status<br>`relay_8_status` | Discrete (1x) | FC02 read | bool (bit) |
