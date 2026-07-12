# Waveshare Modbus POE ETH Relay 30CH — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/waveshare-modbus-poe-eth-relay-30ch.yaml`

## Primary source

- **Waveshare Wiki — Modbus POE ETH Relay (30CH)** (living wiki page (retrieved 2026-07-11))
- Source: [https://www.waveshare.com/wiki/Modbus_POE_ETH_Relay_30CH](https://www.waveshare.com/wiki/Modbus_POE_ETH_Relay_30CH)
- Source type: official-manufacturer (Waveshare product wiki)
- Register addresses vs device file: verified — relays = coils 0x0000–0x001D (FC01 read / FC05 write; 0xFF00 on, 0x0000 off, 0x5500 toggle); software version = holding 0x8000 (÷100)
- Local copy: [`wiki.html`](./wiki.html) — 105 KB

> The full Modbus protocol is documented inline on the wiki (no separate PDF is published). Also documents flash on/off (interval = data × 100 ms) and the all-relays register 0x00FF.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 31 (Holding 1, Coil 30)

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
| `0x0008` (8) — Relay 9<br>`relay_9` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0009` (9) — Relay 10<br>`relay_10` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x000A` (10) — Relay 11<br>`relay_11` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x000B` (11) — Relay 12<br>`relay_12` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x000C` (12) — Relay 13<br>`relay_13` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x000D` (13) — Relay 14<br>`relay_14` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x000E` (14) — Relay 15<br>`relay_15` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x000F` (15) — Relay 16<br>`relay_16` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0010` (16) — Relay 17<br>`relay_17` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0011` (17) — Relay 18<br>`relay_18` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0012` (18) — Relay 19<br>`relay_19` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0013` (19) — Relay 20<br>`relay_20` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0014` (20) — Relay 21<br>`relay_21` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0015` (21) — Relay 22<br>`relay_22` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0016` (22) — Relay 23<br>`relay_23` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0017` (23) — Relay 24<br>`relay_24` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0018` (24) — Relay 25<br>`relay_25` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0019` (25) — Relay 26<br>`relay_26` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x001A` (26) — Relay 27<br>`relay_27` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x001B` (27) — Relay 28<br>`relay_28` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x001C` (28) — Relay 29<br>`relay_29` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x001D` (29) — Relay 30<br>`relay_30` | Coil (0x) | FC01 read · FC05 write | bool (bit) |
