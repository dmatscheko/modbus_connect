# Supported devices

Modbus Connect bundles device files of two very different kinds. Only the
first kind is supported.

- [Tested devices](#tested-devices) — verified on real hardware and maintained
  here.
- [Untested device files](#untested-device-files) — automatic conversions of
  community files. They may be incomplete or wrong.

A device that is in neither list needs a device file of its own: see
[writing a device file](writing_a_device_file.md).

## Tested devices

These six files have been tested on real hardware and are actively maintained.
Each is generated from a hand-written source
(`support/devicedocs/<slug>/device.yaml`).

| Manufacturer | Model | File | Docs | Source |
| --- | --- | --- | --- | --- |
| Anhui | QDF70B Pressure Sensor | `anhui-qdf70b-pressure-sensor.yaml` | [registers](../support/devicedocs/anhui-qdf70b-pressure-sensor/registers.md) · [groups](../support/devicedocs/anhui-qdf70b-pressure-sensor/groups.md) · [caveats](../support/devicedocs/anhui-qdf70b-pressure-sensor/caveats.md) | official |
| Dimplex | Sole/Wasser-Wärmepumpe SI 11TU | `dimplex-si-11tu.yaml` | [registers](../support/devicedocs/dimplex-si-11tu/registers.md) · [groups](../support/devicedocs/dimplex-si-11tu/groups.md) · [caveats](../support/devicedocs/dimplex-si-11tu/caveats.md) | official |
| Pichler | Lüftungsgerät LG 150 – LG 250 | `pichler-lg150-lg250.yaml` | [registers](../support/devicedocs/pichler-lg150-lg250/registers.md) · [groups](../support/devicedocs/pichler-lg150-lg250/groups.md) · [caveats](../support/devicedocs/pichler-lg150-lg250/caveats.md) | official |
| Pichler | Lüftungsgerät LG 350 – LG 450 | `pichler-lg350-lg450.yaml` | [registers](../support/devicedocs/pichler-lg350-lg450/registers.md) · [groups](../support/devicedocs/pichler-lg350-lg450/groups.md) · [caveats](../support/devicedocs/pichler-lg350-lg450/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Pichler-LG350-LG450.yaml), modified |
| SolaX Power | X3-Hybrid G4 | `solax-x3-hybrid-g4.yaml` | [registers](../support/devicedocs/solax-x3-hybrid-g4/registers.md) · [groups](../support/devicedocs/solax-x3-hybrid-g4/groups.md) · [caveats](../support/devicedocs/solax-x3-hybrid-g4/caveats.md) | [homeassistant-solax-modbus](https://github.com/wills106/homeassistant-solax-modbus/blob/main/custom_components/solax_modbus/plugin_solax.py), modified |
| SolaX Power | X3-HAC (11 kW EV charger) | `solax-x3-hac.yaml` | [registers](../support/devicedocs/solax-x3-hac/registers.md) · [groups](../support/devicedocs/solax-x3-hac/groups.md) · [caveats](../support/devicedocs/solax-x3-hac/caveats.md) | [homeassistant-solax-modbus](https://github.com/wills106/homeassistant-solax-modbus/blob/main/custom_components/solax_modbus/plugin_solax_ev_charger.py), modified |

## Untested device files

These 18 files were converted automatically from the community device files
of [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway).
**Nobody here has run them against the hardware.** A file may work as it is,
miss entities, or contain wrong addresses or scalings.

So that this is visible where it matters, each of these files declares itself
untested, and Home Assistant shows **(untested)** after the model — in the
device picker during setup and on the device page.

If you own one of these devices:

- Expect to check the values against the device's own display or app.
  [Troubleshooting](troubleshooting.md) explains unavailable entities and wrong
  values.
- Please [report](https://github.com/dmatscheko/modbus_connect/issues/new/choose)
  what works and what does not — or fix the file and send it in. A file
  becomes *tested* when someone who has the hardware takes it over; see
  [contributing](../CONTRIBUTING.md#changing-a-bundled-device-file).

| Manufacturer | Model | File | Docs | Source |
| --- | --- | --- | --- | --- |
| Eastron | SDM-230 | `eastron-sdm230.yaml` | [registers](../support/devicedocs/eastron-sdm230/registers.md) · [caveats](../support/devicedocs/eastron-sdm230/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/SDM230.yaml) |
| Eastron | SDM-630 | `eastron-sdm630.yaml` | [registers](../support/devicedocs/eastron-sdm630/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/SDM630.yaml) |
| ebyte | ME31-AXAX404 | `ebyte-me31-axax404.yaml` | [registers](../support/devicedocs/ebyte-me31-axax404/registers.md) · [caveats](../support/devicedocs/ebyte-me31-axax404/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/ME31-AXAX404.yaml) |
| Finder | 7M.24 | `finder-7m24.yaml` | [registers](../support/devicedocs/finder-7m24/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/7M_24.yaml) |
| Finder | 7M.38 | `finder-7m38.yaml` | [registers](../support/devicedocs/finder-7m38/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/7M_38.yaml) |
| Fröling | BWP300 PV | `froeling-bwp300-pv.yaml` | [registers](../support/devicedocs/froeling-bwp300-pv/registers.md) · [caveats](../support/devicedocs/froeling-bwp300-pv/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Fr%C3%B6ling_BWP300PV.yaml) |
| Growatt | MIC 2500TL-X | `growatt-mic-2500tl-x.yaml` | [registers](../support/devicedocs/growatt-mic-2500tl-x/registers.md) · [caveats](../support/devicedocs/growatt-mic-2500tl-x/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/MIC-2500TL-X.yaml) |
| Growatt | MIN 6000TL-XH | `growatt-min-6000tl-xh.yaml` | [registers](../support/devicedocs/growatt-min-6000tl-xh/registers.md) · [caveats](../support/devicedocs/growatt-min-6000tl-xh/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/MIN-6000TL-XH.yaml) |
| Growatt | MOD 6000TL-X | `growatt-mod-6000tl-x.yaml` | [registers](../support/devicedocs/growatt-mod-6000tl-x/registers.md) · [caveats](../support/devicedocs/growatt-mod-6000tl-x/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/MOD-6000TL-X.yaml) |
| Growatt | MOD 10KTL3-XH | `growatt-mod-10ktl3-xh.yaml` | [registers](../support/devicedocs/growatt-mod-10ktl3-xh/registers.md) · [caveats](../support/devicedocs/growatt-mod-10ktl3-xh/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/MOD-10KTL3-XH.yaml) |
| Growatt | SPH3600TL BL_UP | `growatt-sph-3600tl-bl-up.yaml` | [registers](../support/devicedocs/growatt-sph-3600tl-bl-up/registers.md) · [caveats](../support/devicedocs/growatt-sph-3600tl-bl-up/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/SPH-3600TL-BL_UP.yaml) |
| Husdata | H60 | `husdata-h60.yaml` | [registers](../support/devicedocs/husdata-h60/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Husdata_H60.yaml) |
| Salda | RIS / RIRS (MCB) | `salda-ris-mcb.yaml` | [registers](../support/devicedocs/salda-ris-mcb/registers.md) · [caveats](../support/devicedocs/salda-ris-mcb/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Salda_RIS_MCB.yaml) |
| Schneider Electric | Altivar ATV312 | `schneider-atv312.yaml` | [registers](../support/devicedocs/schneider-atv312/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Schneider_ATV312.yaml) |
| Schneider Electric | Altivar ATV312 Expert | `schneider-atv312-expert.yaml` | [registers](../support/devicedocs/schneider-atv312-expert/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Schneider_ATV312_expert.yaml) |
| Varmann | Qtherm | `varmann-qtherm.yaml` | [registers](../support/devicedocs/varmann-qtherm/registers.md) · [caveats](../support/devicedocs/varmann-qtherm/caveats.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Varmann%20Qtherm.yaml) |
| Waveshare | Modbus POE ETH Relay 30CH | `waveshare-modbus-poe-eth-relay-30ch.yaml` | [registers](../support/devicedocs/waveshare-modbus-poe-eth-relay-30ch/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Waveshare_30_POE.yaml) |
| Waveshare | Modbus RTU Relay (D) | `waveshare-modbus-rtu-relay-d.yaml` | [registers](../support/devicedocs/waveshare-modbus-rtu-relay-d/registers.md) | [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway/blob/main/custom_components/modbus_local_gateway/device_configs/Waveshare_RTU_Relay_D.yaml) |

The device picker also lists a *Test Model (DO NOT USE)*. It is an example file
the project tests itself with, not a real device.

## Reading the columns

**File** is the name of the bundled device file
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

- **official** — the file was written for this integration from the
  manufacturer's own register document.
- A link — the upstream file it was converted from; *modified* where it has
  been reworked here. The Pichler LG 350 – LG 450 file was first written for
  `modbus_local_gateway` and ported; the two SolaX files started as conversions
  of [homeassistant-solax-modbus](https://github.com/wills106/homeassistant-solax-modbus).
  All three have been heavily modified and tested since.
