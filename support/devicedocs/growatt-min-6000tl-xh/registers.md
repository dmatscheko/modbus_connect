# Growatt MIN 6000TL-XH — Modbus registers

**Device file:** `custom_components/modbus_connect/device_configs/MIN-6000TL-XH.yaml`

## Primary source

- **Growatt Inverter Modbus RTU Protocol (a.k.a. Protocol II)** (V1.24 (first release 2020-04-28))
- Source: [https://github.com/johanmeijer/grott/blob/master/documentatie/Growatt-Inverter-Modbus-RTU-Protocol-II-V1-24-English-new.pdf](https://github.com/johanmeijer/grott/blob/master/documentatie/Growatt-Inverter-Modbus-RTU-Protocol-II-V1-24-English-new.pdf)
- Source type: manufacturer-authored PDF, community-hosted (grott mirror; Growatt does not publish it publicly)
- Register addresses vs device file: verified — 3000-range TL-XH input group + storage extension (3125–3249: vbat/soc/pchr); storage settings live in the 3000-range holding (3036/3037/3047/3048/3049)
- Local copy: [`Growatt-Inverter-Modbus-RTU-Protocol-II-V1.24-English.pdf`](./Growatt-Inverter-Modbus-RTU-Protocol-II-V1.24-English.pdf) — 737 KB

> Growatt does not host the protocol PDF publicly; verbatim grott mirror of the manufacturer document. Big-endian / high-word-first; FC03/FC04 read, FC06/FC16 write. TL-XH storage config is in the 3000-range holding (not the 1000-range).

## Scope & conventions

This table lists the **registers used by Modbus Connect's device file** — what the integration actually reads and writes. The manufacturer's document linked above is the authoritative, complete register map; consult it for registers this integration does not use.

Tables (as named in the datasheet): **Holding** (4x — FC03 read, FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus command* column shows the function codes this integration uses; it notes where a single register is written with FC16 (write-multiple) because the device requires it. *(internal)* registers are polled to feed composite template entities but expose no entity of their own.

**Registers in this file:** 77 (Holding 12, Input 65)

## Registers

| Register | Table | Modbus command | Data type / conversion |
| --- | --- | --- | --- |
| `0x0009` (9) — Firmware version<br>`hw_version` | Holding (4x) | FC03 read | string · 3 regs (6 chars) |
| `0x000C` (12) — Control firmware version<br>`sw_version` | Holding (4x) | FC03 read | string · 3 regs (6 chars) |
| `0x0BB9` (3001) — Serial Number<br>`serial_no` | Holding (4x) | FC03 read | string · 14 regs (28 chars) |
| `0x0000` (0) — Remote On/Off<br>`on_off` | Holding (4x) | FC03 read · FC06 write | uint16 · on=1 |
| `0x0003` (3) — Max output active power<br>`max_output_active` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x000F` (15) — LCD language<br>`language` | Holding (4x) | FC03 read · FC06 write | uint16 · enum · 9 opts |
| `0x0C0D` (3085) — Communicate address<br>`com_address` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0BDC` (3036) — Discharge Power Rate (Grid First)<br>`GridFirstDischargePowerRate` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0BDD` (3037) — Stop Discharge SOC (Grid First)<br>`GridFirstStopSOC` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0BE7` (3047) — Discharge Power Rate (Bat First)<br>`BatFirstDischargePowerRate` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0BE8` (3048) — Stop Charge SOC (Bat First)<br>`BatFirstStopSOC` | Holding (4x) | FC03 read · FC06 write | uint16 |
| `0x0BE9` (3049) — AC Charge Enable<br>`AcChargeEnable` | Holding (4x) | FC03 read · FC06 write | uint16 · on=1 |
| `0x0BB8` (3000) — Inverter Machine Status<br>`machine_status` | Input (3x) | FC04 read | uint16 · mask 0xFF · enum · 4 opts |
| `0x0BB8` (3000) — Inverter Run Status<br>`run_status` | Input (3x) | FC04 read | uint16 · mask 0xFF00 · enum · 8 opts |
| `0x0BB9` (3001) — PV total power<br>`Ppv` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BBB` (3003) — PV1 voltage<br>`Vpv1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0BBC` (3004) — PV1 input current<br>`PV1Curr` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0BBD` (3005) — PV1 power<br>`Ppv1` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BBF` (3007) — PV2 voltage<br>`Vpv2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0BC0` (3008) — PV2 input current<br>`PV2Curr` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0BC1` (3009) — PV2 power<br>`Ppv2` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BCF` (3023) — Output power<br>`Pac` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BD1` (3025) — Grid frequency<br>`Fac` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0BD2` (3026) — Grid voltage<br>`Vac1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0BD3` (3027) — Grid output current<br>`Iac1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0BD4` (3028) — Grid output watt VA<br>`Pac1` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BD6` (3030) — Three phase grid voltage (2)<br>`Vac2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0BD7` (3031) — Three phase grid output current (2)<br>`Iac2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0BD8` (3032) — Three phase grid output power (2)<br>`Pac2` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BDA` (3034) — Three phase grid voltage (3)<br>`Vac3` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0BDB` (3035) — Three phase grid output current (3)<br>`Iac3` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0BDC` (3036) — Three phase grid output power (3)<br>`Pac3` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BDE` (3038) — Three phase grid voltage (RS)<br>`Vac_RS` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0BDF` (3039) — Three phase grid voltage (ST)<br>`Vac_ST` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0BE0` (3040) — Three phase grid voltage (TR)<br>`Vac_TR` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0BE1` (3041) — Total forward power<br>`PtouserTotal` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BE3` (3043) — Total reverse power<br>`PtogridTotal` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BE5` (3045) — Total load power<br>`PtoloadTotal` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BE7` (3047) — Work time total<br>`TimeTotal` | Input (3x) | FC04 read | uint32 · ×0.5 |
| `0x0BE9` (3049) — Today generate energy<br>`EacToday` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BEB` (3051) — Total generate energy<br>`EacTotal` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BED` (3053) — PV Energy total<br>`Epv_total` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BEF` (3055) — PV1Energy today<br>`Epv1_today` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BF1` (3057) — PV1 Energy total<br>`Epv1_total` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BF3` (3059) — PV2Energy today<br>`Epv2_today` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BF5` (3061) — PV2 Energy total<br>`Epv2_total` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BFB` (3067) — Today energy to user<br>`Etouser_today` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BFD` (3069) — Total energy to user<br>`Etouser_total` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0BFF` (3071) — Today energy to grid<br>`Etogrid_today` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0C01` (3073) — Total energy to grid<br>`Etogrid_total` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0C03` (3075) — Today energy of user load<br>`Eload_today` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0C05` (3077) — Total energy of user load<br>`Eload_total` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0C0E` (3086) — Derating Mode<br>`DeratingMode` | Input (3x) | FC04 read | uint16 · enum · 17 opts |
| `0x0C15` (3093) — Inverter temperature<br>`Temp1` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0C16` (3094) — IPM Inverter temperature<br>`Temp2` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0C17` (3095) — Boost temperature<br>`Temp3` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0C19` (3097) — Communications board temperature<br>`Temp5` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0C1A` (3098) — P Bus inside voltage<br>`PBusVoltage` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0C1B` (3099) — N Bus inside voltage<br>`NBusVoltage` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0C1C` (3100) — Inverter output Power Factor<br>`IPF` | Input (3x) | FC04 read | uint16 |
| `0x0C1D` (3101) — Real output power percent<br>`RealOPPercent` | Input (3x) | FC04 read | uint16 |
| `0x0C1E` (3102) — Output Maxpower Limited<br>`OPFullWatt` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0C20` (3104) — Inverter standby flag<br>`StandbyFlag` | Input (3x) | FC04 read | uint16 |
| `0x0C21` (3105) — Fault code<br>`Fault` | Input (3x) | FC04 read | uint16 |
| `0x0C22` (3106) — Warning code<br>`Warning` | Input (3x) | FC04 read | uint16 |
| `0x0C35` (3125) — Today discharge energy<br>`Edischr_today` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0C37` (3127) — Total discharge energy<br>`Edischr_total` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0C39` (3129) — Today charge energy<br>`Echr_today` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0C3B` (3131) — Total charge energy<br>`Echr_total` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0C48` (3144) — Work mode<br>`priority` | Input (3x) | FC04 read | uint16 · enum · 3 opts |
| `0x0C5F` (3167) — Storage Fault code<br>`FaultCode` | Input (3x) | FC04 read | uint16 |
| `0x0C60` (3168) — Storage Warning code<br>`WarningCode` | Input (3x) | FC04 read | uint16 |
| `0x0C61` (3169) — Battery voltage<br>`vbat` | Input (3x) | FC04 read | uint16 · ×0.01 |
| `0x0C62` (3170) — Battery current<br>`ibat` | Input (3x) | FC04 read | uint16 · ×0.1 |
| `0x0C63` (3171) — SoC<br>`soc` | Input (3x) | FC04 read | uint16 |
| `0x0C6A` (3178) — Discharge power<br>`pdischr` | Input (3x) | FC04 read | uint32 · ×0.1 |
| `0x0C6C` (3180) — Charge power<br>`pchr` | Input (3x) | FC04 read | uint32 · ×0.1 |
