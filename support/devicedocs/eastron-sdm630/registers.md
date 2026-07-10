# Eastron SDM-630 — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/SDM630.yaml`

## Primary source

- **Eastron SDM630-Modbus — Modbus Protocol Implementation** (V1.8)
- Source: [https://www.eastroneurope.com/images/uploads/products/protocol/SDM630_MODBUS_Protocol.pdf](https://www.eastroneurope.com/images/uploads/products/protocol/SDM630_MODBUS_Protocol.pdf)
- Source type: official-manufacturer (eastroneurope.com protocol directory, no login)
- Register addresses vs device file: verified — measurements = input float32 pairs 0x0000–0x0180 (FC04, MSB-register first); holding Node 0x14, Baud 0x1C (map exact), serial 0xFC00 uint32
- Local copy: [`SDM630_MODBUS_Protocol.pdf`](./SDM630_MODBUS_Protocol.pdf) — 498 KB

> Served directly from eastroneurope.com’s official product-protocol directory. The SDM630-Modbus ‘V2’ hardware revision shares this same register map. Config = holding FC03 read / FC16 write (float32 = 2 registers).

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 85 (Holding 4, Input 81)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0xFC00` (64512) — Serial Number<br>`serial_num` | Holding (4x) | FC03 read | uint32 |
| `0x0014` (20) — Communicate address<br>`com_address` | Holding (4x) | FC03 read · FC16 write | float32 |
| `0x001C` (28) — Baud Rate<br>`baud_rate` | Holding (4x) | FC03 read · FC16 write | float32 · enum · 5 opts |
| `0x001E` (30) — Energy Units Prefix<br>`unit_prefix` | Holding (4x) | FC03 read · FC16 write | float32 · enum · 2 opts |
| `0x0000` (0) — Phase 1 Voltage | Input (3x) | FC04 read | float32 |
| `0x0002` (2) — Phase 2 Voltage | Input (3x) | FC04 read | float32 |
| `0x0004` (4) — Phase 3 Voltage | Input (3x) | FC04 read | float32 |
| `0x0006` (6) — Phase 1 Current | Input (3x) | FC04 read | float32 |
| `0x0008` (8) — Phase 2 Current | Input (3x) | FC04 read | float32 |
| `0x000A` (10) — Phase 3 Current | Input (3x) | FC04 read | float32 |
| `0x000C` (12) — Phase 1 Active Power | Input (3x) | FC04 read | float32 |
| `0x000E` (14) — Phase 2 Active Power | Input (3x) | FC04 read | float32 |
| `0x0010` (16) — Phase 3 Active Power | Input (3x) | FC04 read | float32 |
| `0x0012` (18) — Phase 1 Apparent Power | Input (3x) | FC04 read | float32 |
| `0x0014` (20) — Phase 2 Apparent Power | Input (3x) | FC04 read | float32 |
| `0x0016` (22) — Phase 3 Apparent Power | Input (3x) | FC04 read | float32 |
| `0x0018` (24) — Phase 1 Reactive Power | Input (3x) | FC04 read | float32 |
| `0x001A` (26) — Phase 2 Reactive Power | Input (3x) | FC04 read | float32 |
| `0x001C` (28) — Phase 3 Reactive Power | Input (3x) | FC04 read | float32 |
| `0x001E` (30) — Phase 1 Power Factor | Input (3x) | FC04 read | float32 |
| `0x0020` (32) — Phase 2 Power Factor | Input (3x) | FC04 read | float32 |
| `0x0022` (34) — Phase 3 Power Factor | Input (3x) | FC04 read | float32 |
| `0x0024` (36) — Phase 1 Phase Angle | Input (3x) | FC04 read | float32 |
| `0x0026` (38) — Phase 2 Phase Angle | Input (3x) | FC04 read | float32 |
| `0x0028` (40) — Phase 3 Phase Angle | Input (3x) | FC04 read | float32 |
| `0x002A` (42) — Average Line to neutral Volts | Input (3x) | FC04 read | float32 |
| `0x002E` (46) — Average Line Current | Input (3x) | FC04 read | float32 |
| `0x0030` (48) — Sum of Line currents | Input (3x) | FC04 read | float32 |
| `0x0034` (52) — Total System Power | Input (3x) | FC04 read | float32 |
| `0x0038` (56) — Total System VA | Input (3x) | FC04 read | float32 |
| `0x003C` (60) — Total System VAr | Input (3x) | FC04 read | float32 |
| `0x003E` (62) — Total System Power factor | Input (3x) | FC04 read | float32 |
| `0x0042` (66) — Total System Phase Angle | Input (3x) | FC04 read | float32 |
| `0x0046` (70) — Frequency | Input (3x) | FC04 read | float32 |
| `0x0048` (72) — Total Import Active Energy | Input (3x) | FC04 read | float32 |
| `0x004A` (74) — Total Export Active Energy | Input (3x) | FC04 read | float32 |
| `0x004C` (76) — Total Import Reactive Energy | Input (3x) | FC04 read | float32 |
| `0x004E` (78) — Total Export Reactive Energy | Input (3x) | FC04 read | float32 |
| `0x0050` (80) — Total VAh | Input (3x) | FC04 read | float32 |
| `0x0052` (82) — Ah | Input (3x) | FC04 read | float32 |
| `0x0054` (84) — Total System Power demand | Input (3x) | FC04 read | float32 |
| `0x0056` (86) — Maximum Total System Power demand | Input (3x) | FC04 read | float32 |
| `0x0064` (100) — Total System VA demand | Input (3x) | FC04 read | float32 |
| `0x0066` (102) — Maximum Total System VA demand | Input (3x) | FC04 read | float32 |
| `0x0068` (104) — Neutral Current demand | Input (3x) | FC04 read | float32 |
| `0x006A` (106) — Maximum neutral Current demand | Input (3x) | FC04 read | float32 |
| `0x00C8` (200) — Line 1 to Line 2 Volts | Input (3x) | FC04 read | float32 |
| `0x00CA` (202) — Line 2 to Line 3 Volts | Input (3x) | FC04 read | float32 |
| `0x00CC` (204) — Line 3 to Line 1 Volts | Input (3x) | FC04 read | float32 |
| `0x00CE` (206) — Average Line to Line Volts | Input (3x) | FC04 read | float32 |
| `0x00E0` (224) — Neutral Current | Input (3x) | FC04 read | float32 |
| `0x00EA` (234) — Phase 1 L/N Volts THD | Input (3x) | FC04 read | float32 |
| `0x00EC` (236) — Phase 2 L/N Volts THD | Input (3x) | FC04 read | float32 |
| `0x00EE` (238) — Phase 3 L/N Volts THD | Input (3x) | FC04 read | float32 |
| `0x00F0` (240) — Phase 1 Current THD | Input (3x) | FC04 read | float32 |
| `0x00F2` (242) — Phase 2 Current THD | Input (3x) | FC04 read | float32 |
| `0x00F4` (244) — Phase 3 Current THD | Input (3x) | FC04 read | float32 |
| `0x00F8` (248) — Average Line to neutral Volts THD | Input (3x) | FC04 read | float32 |
| `0x00FA` (250) — Average Line Current THD | Input (3x) | FC04 read | float32 |
| `0x0102` (258) — Phase 1 Current demand | Input (3x) | FC04 read | float32 |
| `0x0104` (260) — Phase 2 Current demand | Input (3x) | FC04 read | float32 |
| `0x0106` (262) — Phase 3 Current demand | Input (3x) | FC04 read | float32 |
| `0x0108` (264) — Phase 1 Maximum Current Demand | Input (3x) | FC04 read | float32 |
| `0x010A` (266) — Phase 2 Maximum Current Demand | Input (3x) | FC04 read | float32 |
| `0x010C` (268) — Phase 3 Maximum Current Demand | Input (3x) | FC04 read | float32 |
| `0x0156` (342) — Total kWh<br>`Total Energy` | Input (3x) | FC04 read | float32 |
| `0x0158` (344) — Total kVArh | Input (3x) | FC04 read | float32 |
| `0x015A` (346) — L1 Import kWh<br>`L1 Import Energy` | Input (3x) | FC04 read | float32 |
| `0x015C` (348) — L2 Import kWh<br>`L2 Import Energy` | Input (3x) | FC04 read | float32 |
| `0x015E` (350) — L3 Import kWh<br>`L3 Import Energy` | Input (3x) | FC04 read | float32 |
| `0x0160` (352) — L1 Export kWh<br>`L1 Export Energy` | Input (3x) | FC04 read | float32 |
| `0x0162` (354) — L2 Export kWh<br>`L2 Export Energy` | Input (3x) | FC04 read | float32 |
| `0x0164` (356) — L3 Export kWh<br>`L3 Export Energy` | Input (3x) | FC04 read | float32 |
| `0x0166` (358) — L1 Total kWh<br>`L1 Total Energy` | Input (3x) | FC04 read | float32 |
| `0x0168` (360) — L2 Total kWh<br>`L2 Total Energy` | Input (3x) | FC04 read | float32 |
| `0x016A` (362) — L3 Total kWh<br>`L3 Total Energy` | Input (3x) | FC04 read | float32 |
| `0x016C` (364) — L1 Import kVArh | Input (3x) | FC04 read | float32 |
| `0x016E` (366) — L2 Import kVArh | Input (3x) | FC04 read | float32 |
| `0x0170` (368) — L3 Import kVArh | Input (3x) | FC04 read | float32 |
| `0x0172` (370) — L1 Export kVArh | Input (3x) | FC04 read | float32 |
| `0x0174` (372) — L2 Export kVArh | Input (3x) | FC04 read | float32 |
| `0x0176` (374) — L3 Export kVArh | Input (3x) | FC04 read | float32 |
| `0x0178` (376) — L1 Total kVArh | Input (3x) | FC04 read | float32 |
| `0x017A` (378) — L2 Total kVArh | Input (3x) | FC04 read | float32 |
| `0x017C` (380) — L3 Total kVArh | Input (3x) | FC04 read | float32 |
