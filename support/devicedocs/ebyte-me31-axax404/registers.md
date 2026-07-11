# ebyte ME31-AXAX404 — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/ME31-AXAX404.yaml`

## Primary source

- **EBYTE — ME31-AXAX4040 User Manual (EN)** (V1.6)
- Source: [https://www.cdebyte.com/products/ME31-AXAX4040/4](https://www.cdebyte.com/products/ME31-AXAX4040/4)
- Source type: official-manufacturer (cdebyte.com)
- Register addresses vs device file: verified — 4 relay outputs = coils 0x0000–0x0003 (FC01 read / FC05 write); 4 digital inputs documented as discrete inputs 0x0000–0x0003 (FC02)
- Local copy: [`ME31-AXAX4040_User_Manual_EN_V1.6.pdf`](./ME31-AXAX4040_User_Manual_EN_V1.6.pdf) — 1.8 MB — primary source
- Local copy: [`caveats.md`](./caveats.md) — 755 bytes

> The product code is ME31-AXAX4040 (4 relay out / 4 dry-contact in); the device-file name ‘ME31-AXAX404’ is a truncation. Note: the device file models the 4 digital inputs as coils (FC01) at addr 0–3, whereas the manual documents them as discrete inputs (FC02) at the same addresses.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 8 (Coil 8)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x0000` (0) — coil1 | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0001` (1) — coil2 | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0002` (2) — coil3 | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0003` (3) — coil4 | Coil (0x) | FC01 read · FC05 write | bool (bit) |
| `0x0000` (0) — ebyte_ip1 | Coil (0x) | FC01 read | bool (bit) |
| `0x0001` (1) — ebyte_ip2 | Coil (0x) | FC01 read | bool (bit) |
| `0x0002` (2) — ebyte_ip3 | Coil (0x) | FC01 read | bool (bit) |
| `0x0003` (3) — ebyte_ip4 | Coil (0x) | FC01 read | bool (bit) |
