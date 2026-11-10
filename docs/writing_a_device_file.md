# Writing a device file

Your device is not in the [supported devices](supported_devices.md) list? Then
it needs a **device file**: one YAML file that says which registers the device
has and which Home Assistant entities they become. This page walks you from
nothing to a working file. The [device file reference](device_files.md) is the
place to look up every key afterwards.

1. [Find the register documentation](#1-find-the-register-documentation)
2. [Look at the live device](#2-look-at-the-live-device)
3. [Write the file](#3-write-the-file)
4. [Load it and fix what it reports](#4-load-it-and-fix-what-it-reports)
5. [Refine it](#5-refine-it)
6. [Share it](#6-share-it)

## 1. Find the register documentation

You need the device's Modbus register list: a chapter of the manual, or a PDF
or spreadsheet from the vendor. It tells you each value's address, table
(holding, input, coil or discrete), data type and scaling. Without it, a file
is guesswork — though the scanner in the next step makes guessing a lot easier.

## 2. Look at the live device

You rarely have to write a file blind. Two tools in this repository talk to
the device directly. They are not installed with the integration; run them on
your computer from a checkout of this repository. That needs a one-time
setup, which creates the `.venv/bin/python` the commands below use (Python
3.14 or newer is required):

```bash
git clone https://github.com/dmatscheko/modbus_connect
cd modbus_connect
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements_test.txt
```

If that fails, or you are on Windows, see
[Development → Set up](development.md#set-up).

**The Modbus Scanner** is a browser-based register scanner. It walks the
address space over a Modbus TCP gateway and shows which registers answer,
which change and how fast, and what each one decodes to as every type at once.
You map registers to entities by clicking them, and it generates a ready-to-load
device file from your mappings.

```bash
.venv/bin/python support/modbus_scanner/scanner.py            # set the host in the browser
.venv/bin/python support/modbus_scanner/scanner.py --demo     # try it without hardware
```

The [scanner guide](../support/modbus_scanner/README.md) walks through it.

**`support/modbus_cli.py`** is the terminal counterpart for one-off probes,
reads and writes. It shows a read with every common decoding next to the raw
words, so the right `type` and `swap` can be read straight off, and its `scan`
command prints ready-to-paste `bad_addresses:` and `split_before:` hints. It is
a single file that needs only pymodbus:

```bash
.venv/bin/python support/modbus_cli.py --host <gateway> --help
```

## 3. Write the file

Start small — a `device:` block and one entity are a complete file:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/dmatscheko/modbus_connect/main/docs/device_files.schema.json
device:
  manufacturer: Eastron
  model: SDM630

input:
  phase_1_voltage:
    address: 0x0000
    type: float32
    ha:
      platform: sensor
      name: Phase 1 voltage
      device_class: voltage
      unit_of_measurement: V
```

- Entities are sorted by Modbus table, like the datasheet: `holding:`,
  `input:`, `coil:`, `discrete:`.
- The key (`phase_1_voltage`) identifies the entity; everything under `ha:` is
  a field of the Home Assistant entity.
- The first line gives you autocomplete and inline validation in editors with
  a YAML language server (VS Code needs the YAML extension).

The bundled files in
[`custom_components/modbus_connect/device_configs/`](../custom_components/modbus_connect/device_configs/)
are working examples of everything the format can do.

## 4. Load it and fix what it reports

Save the file as `<ha_config>/modbus_connect/<name>.yaml` (create the folder if
needed) and [add the integration](../README.md#setup). Your file appears in the
device list next to the bundled ones.

- **Your files survive updates** of the integration.
- **A file with the same name as a bundled one overrides it** — handy for
  trying a fix to a bundled file.
- **Errors are loud by design.** An invalid file never loads silently: the
  setup dialog names the file, the entity and the reason, and for fields with
  fixed choices it lists every valid value. A file whose `device:` block is
  broken is left out of the list, with the reason in a note below it; an error
  further down is reported when you select the file.
- **After editing a file that is in use**, reload the integration entry to
  pick up the change.

Once the file loads, *Download diagnostics* on the device page shows the parsed
definition, the read plan and the current values. Wrong values and unavailable
entities are covered in [troubleshooting](troubleshooting.md).

## 5. Refine it

The [device file reference](device_files.md) covers what makes a file good:

- **Writable entities** — numbers, selects, switches, buttons, with the same
  conversions as reading.
- **Composite entities** — a thermostat, fan or cover built from several
  registers with [templates](device_files.md#the-template-section).
- **[Entity groups](device_files.md#entity-groups)** — so users can hide what
  they do not need.
- **[Read tuning](device_files.md#read-planning-and-polling)** — block sizes,
  poll intervals, addresses to avoid.
- **[Translations](device_files.md#translations)** — names and option labels
  in more than one language.

## 6. Share it

Pull requests with new device files are welcome —
[CONTRIBUTING](../CONTRIBUTING.md#adding-a-device-file) explains where the
file goes and what to run. If you are stuck, open a
[device file request](https://github.com/dmatscheko/modbus_connect/issues/new/choose)
with your draft, however incomplete.
