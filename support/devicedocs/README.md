# Device documentation

One folder per bundled device, holding everything that belongs to it: the
**source** the bundled file is generated from, the **primary register document**
it was checked against, and generated **references**. The list of devices, with
links into these folders, is the table in the
[main README](../../README.md#bundled-device-files).

## What is in a device folder

| File | What it is | Edit? |
| --- | --- | --- |
| `device.yaml` | The hand-maintained source of truth of an **owned** device (the six tested ones) — same format as the bundled file, which is generated from it | yes — then regenerate |
| `augment.yaml` | The policy of an **imported** device: what to add, remove, patch, group or translate on top of the upstream file it is converted from | yes — then regenerate |
| `registers.md` | Every register the bundled file reads or writes: address, table, Modbus function code, data type and conversion — plus the primary source and how far the addresses were verified against it | generated, never by hand |
| `groups.md` | The entity groups of a grouped file: tiers, subsystem groups, and which entities each switch reveals | generated, never by hand |
| `caveats.md` | Hand-written notes on device quirks, firmware differences, and known gaps | yes |
| PDF / XLSX / HTML | A local copy of the manufacturer's register document, so the reference stays checkable when the vendor's link dies | — |

A folder has either a `device.yaml` or an `augment.yaml`, never both. The bundled
files in `custom_components/modbus_connect/device_configs/` are **generated** from
these folders and must not be edited directly; the
[converter README](../converter/README.md) explains how to regenerate them and
the two references.

`translations.yaml` next to the device folders is the shared German/English
vocabulary every device file draws on (enum values, group labels, common entity
names); device-specific strings live in the device's own `device.yaml` or
`augment.yaml`.

## Reading a `registers.md`

The **Primary source** block at the top names the document, links it, says who
published it, and states how the device file was checked against it:

- **official** — downloaded from the manufacturer's own site, CDN or wiki.
- **manufacturer-authored, community-hosted** — a genuine manufacturer document
  the vendor does not publish publicly (SolaX, Growatt), mirrored by a reputable
  community project.
- **none** — no public register document could be found; the map is community
  knowledge and the file is the only reference.

**Register addresses vs device file** says whether the addresses were
*verified* (every used register matched) or *partially* checked, and lists
discrepancies found on the way. Treat a *partial* file as a starting point and
report what you find on real hardware.

The table below it lists only what the *device file* uses; the manufacturer's
document remains the complete map.
