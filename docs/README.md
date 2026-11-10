# Modbus Connect documentation

New here? The [main README](../README.md) covers installation and setup.

## Using the integration

| Page | What it answers |
| --- | --- |
| [Supported devices](supported_devices.md) | Which devices are tested, which bundled files are untested conversions, and where their register docs are |
| [Entity groups](entity_groups.md) | How to show and hide parts of a device |
| [Examples](examples.md) | Wiring the Energy Dashboard; automation examples |
| [Troubleshooting](troubleshooting.md) | Connection problems, unavailable entities, wrong values, diagnostics, known limitations |
| [How it works](how_it_works.md) | Polling, writes, the read-health sensors, quarantined registers |

## Adding your own device

| Page | What it answers |
| --- | --- |
| [Writing a device file](writing_a_device_file.md) | From the register list to a working file, step by step |
| [Device file reference](device_files.md) | Every key of the format |
| [Modbus Scanner guide](../support/modbus_scanner/README.md) | The browser tool for exploring a device and generating a file |

## Working on the project

| Page | What it answers |
| --- | --- |
| [Contributing](../CONTRIBUTING.md) | How to submit a device file or a code change |
| [Development](development.md) | Checks, code layout, tooling, releases |
| [Converters and generators](../support/converter/README.md) | How the bundled device files are produced |
| [Device documentation](../support/devicedocs/README.md) | What is in each device's folder and how to read a `registers.md` |
| [Controller-style extensions](../support/controller_extensions.md) | A design note on control loops that do not fit a device file |
