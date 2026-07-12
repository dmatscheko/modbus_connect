# Schneider Electric Altivar ATV312 Expert — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/schneider-atv312-expert.yaml`

## Primary source

- **Schneider Electric — Altivar 312 Communication Variables Manual (BBV51701)** (V1, 06/2009)
- Source: [https://www.se.com/ww/en/download/document/BBV51701/](https://www.se.com/ww/en/download/document/BBV51701/)
- Source type: official-manufacturer (download.schneider-electric.com)
- Register addresses vs device file: verified — same drive & manual as schneider-atv312; the Expert subset (6001/6003/6004/6005 comm-config, 8541/8542 control image, 5240 keypad, 5242–5244 analog inputs, 5261 AO1R) all appear in BBV51701
- Local copy: [`ATV312_communication_variables_EN_BBV51701.pdf`](./ATV312_communication_variables_EN_BBV51701.pdf) — 728 KB — primary source
- Local copy: [`ATV312_Modbus_communication_manual_EN_BBV52816.pdf`](./ATV312_Modbus_communication_manual_EN_BBV52816.pdf) — 442 KB

> Same physical drive as Schneider ATV312 — the ‘Expert’ device file is a curated register subset. The register-list manual BBV51701 and the companion BBV52816 (Modbus framing/wiring) are duplicated in this folder for self-containment. FC03 read, FC06/FC16 write.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 11 (Holding 11)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x1771` (6001) — Modbus Drive Address<br>`add_modbus_drive_address` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x1773` (6003) — Modbus Transmission Speed<br>`tbr_modbus_transmission_speed` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x1774` (6004) — Modbus Communication Format<br>`tfo_modbus_communication_format` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x1775` (6005) — Modbus Time-out<br>`tto_modbus_timeout` | Holding (4x) | FC03 read · FC06 write | uint16 · ×0.1 |
| `0x215D` (8541) — CMI1 Modbus Extended Control Image<br>`cmi1_modbus_extended_control_image` | Holding (4x) | FC03 read | uint16 · bitfield · 8 flags |
| `0x215E` (8542) — CMI2 CANopen Extended Control Image<br>`cmi2_canopen_extended_control_image` | Holding (4x) | FC03 read | uint16 · bitfield · 8 flags |
| `0x1478` (5240) — Keypad Present<br>`keypad_present` | Holding (4x) | FC03 read | uint16 · mask 0x80 · on=1 |
| `0x147A` (5242) — AI1C Analog Input AI1<br>`ai1c_analog_input_ai1` | Holding (4x) | FC03 read | uint16 |
| `0x147B` (5243) — AI2C Analog Input AI2<br>`ai2c_analog_input_ai2` | Holding (4x) | FC03 read | int16 |
| `0x147C` (5244) — AI3C Analog Input AI3<br>`ai3c_analog_input_ai3` | Holding (4x) | FC03 read | uint16 |
| `0x148D` (5261) — AO1R Analog Output Value<br>`ao1r_analog_output_value` | Holding (4x) | FC03 read | uint16 |
