# Fröling GmbH BWP300 PV — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/Fröling_BWP300PV.yaml`

## Primary source

No public primary-source register document from the manufacturer could be confirmed for this device.

- Best available reference: [https://www.froeling.com/de-at/produkte/speichersysteme/brauchwasserwaermepumpe-bwp-300-pv/](https://www.froeling.com/de-at/produkte/speichersysteme/brauchwasserwaermepumpe-bwp-300-pv/)

> Fröling publishes no Modbus register document for the BWP 300 PV (an OEM domestic-hot-water heat pump). Its official technical documents are storage-tank installation manuals with no Modbus content. The upstream modbus_local_gateway config — from which this device file derives — cites no source, and its register map (holding 4–33, input 0–119) points to a third-party controller and appears vendor-supplied/reverse-engineered. Any Fröling Modbus spec, if one exists, is behind the login-gated connect.froeling.com partner portal. The table below therefore reflects the device file only; treat its addresses as community-provided, not manufacturer-confirmed.

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 44 (Holding 29, Input 15)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x0004` (4) — Temperatur: T Soll<br>`t_setpoint_set` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0005` (5) — Temperatur: T min<br>`t_min_set` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0006` (6) — Temperatur: T2 min<br>`t2_min_set` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0007` (7) — Zeitplanung: Zustand<br>`timer_enable` | Holding (4x) | FC03 read · FC06 write | uint16 · on=1 |
| `0x0008` (8) — Zeitplanung: Start Heizpatrone (Stunde)<br>`start_hp_hour` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0009` (9) — Zeitplanung: Start Heizpatrone (Minute)<br>`start_hp_min` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x000A` (10) — Zeitplanung: Stop Heizpatrone (Stunde)<br>`stop_hp_hour` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x000B` (11) — Zeitplanung: Stop Heizpatrone (Minute)<br>`stop_hp_min` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x000C` (12) — Betriebsmodus: Standard<br>`betriebsart` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 6 opts |
| `0x000D` (13) — Temperatur: T Legio<br>`legionel_auto_funktion` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x000E` (14) — Tmin RL<br>`wwprotec_tmin_rl` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x000F` (15) — WP_LS<br>`wp_ls` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x0010` (16) — KWL (Raumlüftung)<br>`kwl` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x0011` (17) — Betriebsmodus: PV/SG<br>`pv_modus` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 4 opts |
| `0x0012` (18) — Temperatur: T.PV_WP<br>`t_pv_wp` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0013` (19) — Temperatur: T.PV_EL<br>`t_pv_el` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0014` (20) — Abwesenheit: Zustand<br>`feriendauer` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 6 opts |
| `0x0015` (21) — Abwesenheit: Manuell<br>`abw_tage` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0016` (22) — Boost<br>`boost_enable` | Holding (4x) | FC03 read · FC06 write | uint16 · on=1 |
| `0x0017` (23) — Lüfterpause<br>`fanpause` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 7 opts |
| `0x0019` (25) — Sprache<br>`language` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 12 opts |
| `0x001A` (26) — Abtauart<br>`defrost_mode` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 3 opts |
| `0x001B` (27) — Anode<br>`anode` | Holding (4x) | FC03 read · FC06 write | uint16 · on=1 |
| `0x001C` (28) — Temperatur: T max<br>`t_max` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x001D` (29) — Lüftertyp<br>`fantype` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 2 opts |
| `0x001E` (30) — EC LS1<br>`ec_ls1` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x001F` (31) — EC LS2<br>`ec_ls2` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0020` (32) — EC LS3<br>`ec_ls3` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0021` (33) — Legionellenfunktion: Intervall<br>`legi_tage` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0000` (0) — Kontakt 1: Pressostat<br>`di1_pressostat` | Input (3x) | FC04 read | uint16 · mask 0x1 · on=1 |
| `0x0001` (1) — Kontakt 2: SG-Ready<br>`di2_pv` | Input (3x) | FC04 read | uint16 · mask 0x1 · on=1 |
| `0x0007` (7) — Temperatur: T1 (Verdampfer)<br>`t1` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0008` (8) — Temperatur: T2 (Speicher)<br>`t2` | Input (3x) | FC04 read | int16 · ×0.1 |
| `0x0009` (9) — Relais 1: Kompressor<br>`relay1_kompressor` | Input (3x) | FC04 read | uint16 · mask 0x1 · on=1 |
| `0x000A` (10) — Relais 2: Heizstab (EL)<br>`relay2_elpatron` | Input (3x) | FC04 read | uint16 · mask 0x1 · on=1 |
| `0x000B` (11) — Relais 3: Kessel<br>`relay3_kessel` | Input (3x) | FC04 read | uint16 · mask 0x1 · on=1 |
| `0x000C` (12) — Relais 4: Magnetventil<br>`relay4_magnetventil` | Input (3x) | FC04 read | uint16 · mask 0x1 · on=1 |
| `0x000D` (13) — Relais 6: Kondensator<br>`relay6_kondensator` | Input (3x) | FC04 read | uint16 · mask 0x1 · on=1 |
| `0x000E` (14) — Relais 7: Ventilator<br>`relay7_ventilator` | Input (3x) | FC04 read | uint16 · mask 0x1 · on=1 |
| `0x0010` (16) — Status<br>`status` | Input (3x) | FC04 read | uint16 · bitfield · 15 flags |
| `0x0011` (17) — Abwesenheit: Verbleibend<br>`holyday_remaining_days` | Input (3x) | FC04 read | uint16 |
| `0x0012` (18) — Unit Alarm<br>`alarm` | Input (3x) | FC04 read | uint16 · bitfield · 9 flags |
| `0x0012` (18) — Unit Alarm (raw)<br>`alarm_raw` | Input (3x) | FC04 read | uint16 |
| `0x0077` (119) — FW Version<br>`fw_version` | Input (3x) | FC04 read | uint16 |
