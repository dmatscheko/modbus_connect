# Supported devices

These device definitions ship with Modbus Connect — pick one in the first step
of the [setup](../README.md#setup). A device that is not listed works too, once
it has a device file: see [writing a device file](writing_a_device_file.md).
Pull requests with new files are welcome ([contributing](../CONTRIBUTING.md)).

## Tested and untested

- **✓ Tested** — the six files marked ✓ have been tested on real hardware and
  are actively maintained here. Each is generated from a hand-written source
  (`support/devicedocs/<slug>/device.yaml`).
- **Untested** — every other file is a conversion of a community file from
  [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway). It
  should work, but has **not** been verified against hardware here. Treat it as
  a starting point and please
  [report corrections](https://github.com/dmatscheko/modbus_connect/issues/new/choose).

## The list

| Manufacturer | Model | File | Tested | Docs | Source |
| --- | --- | --- | :---: | --- | --- |
| Anhui | QDF70B Pressure Sensor | `anhui-qdf70b-pressure-sensor.yaml` | ✓ | [registers](../support/devicedocs/anhui-qdf70b-pressure-sensor/registers.md) · [groups](../support/devicedocs/anhui-qdf70b-pressure-sensor/groups.md) · [caveats](../support/devicedocs/anhui-qdf70b-pressure-sensor/caveats.md) | official |
| Dimplex | Sole/Wasser-Wärmepumpe SI 11TU | `dimplex-si-11tu.yaml` | ✓ | [registers](../support/devicedocs/dimplex-si-11tu/registers.md) · [groups](../support/devicedocs/dimplex-si-11tu/groups.md) · [caveats](../support/devicedocs/dimplex-si-11tu/caveats.md) | official |
| Eastron | SDM-230 | `eastron-sdm230.yaml` | untested | [registers](../support/devicedocs/eastron-sdm230/registers.md) · [caveats](../support/devicedocs/eastron-sdm230/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/SDM230.yaml) |
| Eastron | SDM-630 | `eastron-sdm630.yaml` | untested | [registers](../support/devicedocs/eastron-sdm630/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/SDM630.yaml) |
| ebyte | ME31-AXAX404 | `ebyte-me31-axax404.yaml` | untested | [registers](../support/devicedocs/ebyte-me31-axax404/registers.md) · [caveats](../support/devicedocs/ebyte-me31-axax404/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/ME31-AXAX404.yaml) |
| Finder | 7M.24 | `finder-7m24.yaml` | untested | [registers](../support/devicedocs/finder-7m24/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/7M_24.yaml) |
| Finder | 7M.38 | `finder-7m38.yaml` | untested | [registers](../support/devicedocs/finder-7m38/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/7M_38.yaml) |
| Fröling | BWP300 PV | `froeling-bwp300-pv.yaml` | untested | [registers](../support/devicedocs/froeling-bwp300-pv/registers.md) · [caveats](../support/devicedocs/froeling-bwp300-pv/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Fr%C3%B6ling_BWP300PV.yaml) |
| Growatt | MIC 2500TL-X | `growatt-mic-2500tl-x.yaml` | untested | [registers](../support/devicedocs/growatt-mic-2500tl-x/registers.md) · [caveats](../support/devicedocs/growatt-mic-2500tl-x/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/MIC-2500TL-X.yaml) |
| Growatt | MIN 6000TL-XH | `growatt-min-6000tl-xh.yaml` | untested | [registers](../support/devicedocs/growatt-min-6000tl-xh/registers.md) · [caveats](../support/devicedocs/growatt-min-6000tl-xh/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/MIN-6000TL-XH.yaml) |
| Growatt | MOD 6000TL-X | `growatt-mod-6000tl-x.yaml` | untested | [registers](../support/devicedocs/growatt-mod-6000tl-x/registers.md) · [caveats](../support/devicedocs/growatt-mod-6000tl-x/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/MOD-6000TL-X.yaml) |
| Growatt | MOD 10KTL3-XH | `growatt-mod-10ktl3-xh.yaml` | untested | [registers](../support/devicedocs/growatt-mod-10ktl3-xh/registers.md) · [caveats](../support/devicedocs/growatt-mod-10ktl3-xh/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/MOD-10KTL3-XH.yaml) |
| Growatt | SPH3600TL BL_UP | `growatt-sph-3600tl-bl-up.yaml` | untested | [registers](../support/devicedocs/growatt-sph-3600tl-bl-up/registers.md) · [caveats](../support/devicedocs/growatt-sph-3600tl-bl-up/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/SPH-3600TL-BL_UP.yaml) |
| Husdata | H60 | `husdata-h60.yaml` | untested | [registers](../support/devicedocs/husdata-h60/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Husdata_H60.yaml) |
| Pichler | Lüftungsgerät LG 150 – LG 250 | `pichler-lg150-lg250.yaml` | ✓ | [registers](../support/devicedocs/pichler-lg150-lg250/registers.md) · [groups](../support/devicedocs/pichler-lg150-lg250/groups.md) · [caveats](../support/devicedocs/pichler-lg150-lg250/caveats.md) | official |
| Pichler | Lüftungsgerät LG 350 – LG 450 | `pichler-lg350-lg450.yaml` | ✓ | [registers](../support/devicedocs/pichler-lg350-lg450/registers.md) · [groups](../support/devicedocs/pichler-lg350-lg450/groups.md) · [caveats](../support/devicedocs/pichler-lg350-lg450/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Pichler-LG350-LG450.yaml), modified |
| Salda | RIS / RIRS (MCB) | `salda-ris-mcb.yaml` | untested | [registers](../support/devicedocs/salda-ris-mcb/registers.md) · [caveats](../support/devicedocs/salda-ris-mcb/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Salda_RIS_MCB.yaml) |
| Schneider Electric | Altivar ATV312 | `schneider-atv312.yaml` | untested | [registers](../support/devicedocs/schneider-atv312/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Schneider_ATV312.yaml) |
| Schneider Electric | Altivar ATV312 Expert | `schneider-atv312-expert.yaml` | untested | [registers](../support/devicedocs/schneider-atv312-expert/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Schneider_ATV312_expert.yaml) |
| SolaX Power | X3-Hybrid G4 | `solax-x3-hybrid-g4.yaml` | ✓ | [registers](../support/devicedocs/solax-x3-hybrid-g4/registers.md) · [groups](../support/devicedocs/solax-x3-hybrid-g4/groups.md) · [caveats](../support/devicedocs/solax-x3-hybrid-g4/caveats.md) | [homeassistant-solax-modbus](https://github.com/wills106/homeassistant-solax-modbus/blob/main/custom_components/solax_modbus/plugin_solax.py), modified |
| SolaX Power | X3-HAC (11 kW EV charger) | `solax-x3-hac.yaml` | ✓ | [registers](../support/devicedocs/solax-x3-hac/registers.md) · [groups](../support/devicedocs/solax-x3-hac/groups.md) · [caveats](../support/devicedocs/solax-x3-hac/caveats.md) | [homeassistant-solax-modbus](https://github.com/wills106/homeassistant-solax-modbus/blob/main/custom_components/solax_modbus/plugin_solax_ev_charger.py), modified |
| Varmann | Qtherm | `varmann-qtherm.yaml` | untested | [registers](../support/devicedocs/varmann-qtherm/registers.md) · [caveats](../support/devicedocs/varmann-qtherm/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Varmann%20Qtherm.yaml) |
| Waveshare | Modbus POE ETH Relay 30CH | `waveshare-modbus-poe-eth-relay-30ch.yaml` | untested | [registers](../support/devicedocs/waveshare-modbus-poe-eth-relay-30ch/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Waveshare_30_POE.yaml) |
| Waveshare | Modbus RTU Relay (D) | `waveshare-modbus-rtu-relay-d.yaml` | untested | [registers](../support/devicedocs/waveshare-modbus-rtu-relay-d/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Waveshare_RTU_Relay_D.yaml) |

The device picker also lists a *Test Model (DO NOT USE)*. It is an example file
the project tests itself with, not a real device.

## Reading the columns

**File** is the name of the bundled definition
(in [`custom_components/modbus_connect/device_configs/`](../custom_components/modbus_connect/device_configs/)).
A file of your own with the same name in `<ha_config>/modbus_connect/`
overrides it.

**Docs** links what is known about the device:

- *registers* — every register the file reads or writes, generated from the
  file, with the manufacturer document it was checked against.
- *groups* — for files that use [entity groups](entity_groups.md): which
  entities each switch reveals.
- *caveats* — hand-written notes on quirks, firmware differences and known
  gaps.

How to read these pages is explained in the
[device documentation overview](../support/devicedocs/README.md).

**Source** says where the file comes from:

- A link — the upstream file it was converted from; *modified* where it has
  been reworked here. The Pichler LG 350 – LG 450 file was first written for
  `modbus_local_gateway` and ported; the two SolaX files started as conversions
  of [homeassistant-solax-modbus](https://github.com/wills106/homeassistant-solax-modbus).
  All three have been heavily modified since.
- **official** — the file was written for this integration from the
  manufacturer's own register document.
