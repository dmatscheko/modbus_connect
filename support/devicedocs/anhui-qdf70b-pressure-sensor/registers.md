# Anhui QDF70B Pressure Sensor — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/anhui-qdf70b-pressure-sensor.yaml`

## Primary source

No public primary-source register document from the manufacturer could be confirmed for this device.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 3 (Holding 3)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x0004` (4) — Pressure<br>`holding_0004` | Holding (4x) | FC03 read | uint16 |
| `0x0016` (22) — Pressure detail 2<br>`holding_0016` | Holding (4x) | FC03 read | uint16 |
| `0x0009` (9) — Pressure detail 1<br>`holding_0009` | Holding (4x) | FC03 read | int16 |
