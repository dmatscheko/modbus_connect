# Troubleshooting

Find your symptom below. If you end up opening an
[issue](https://github.com/dmatscheko/modbus_connect/issues/new/choose), attach
the [diagnostics file](#diagnostics) — it answers most questions in one
attachment.

- [Setup: "Failed to connect"](#setup-failed-to-connect)
- [Setup: "no device answered under this Modbus device ID"](#setup-no-device-answered-under-this-modbus-device-id)
- [Setup: "This device file could not be loaded"](#setup-this-device-file-could-not-be-loaded)
- [Some entities are unavailable](#some-entities-are-unavailable)
- [Everything is unavailable](#everything-is-unavailable)
- [Values are wrong](#values-are-wrong)
- [An entity I expect is missing](#an-entity-i-expect-is-missing)
- [Diagnostics](#diagnostics) · [Debug logging](#debug-logging)
- [Known limitations](#known-limitations)

## Setup: "Failed to connect"

The gateway or adapter could not be opened.

- Check the host and port, or the serial port path.
- Make sure nothing else holds the gateway's only connection. Many cheap
  RS-485 gateways accept exactly one client at a time.
- For a transparent bridge (or `ser2net`), choose *Modbus RTU over TCP* as the
  protocol, not *Modbus TCP*.

## Setup: "no device answered under this Modbus device ID"

The connection works, but the device stayed silent.

- Check the Modbus device ID — this is the usual cause.
- Check that the device is powered and that the RS-485 side of the gateway is
  wired and uses the right baud rate and parity.

## Setup: "This device file could not be loaded"

The device file you picked has an error. The note under the device list names
the file, the entity and the reason. Bundled files are always valid; this
concerns your own files in `<ha_config>/modbus_connect/` — see
[writing a device file](writing_a_device_file.md#4-load-it-and-fix-what-it-reports).

## Some entities are unavailable

The device rejected their addresses: the device file does not match this
model, or the register only exists on other firmware. The integration
[quarantines](how_it_works.md#registers-the-device-refuses) such a register so
the rest keeps working.

- A repair issue under *Settings → System → Repairs* and the log both name the
  entity and its address.
- The [diagnostics file](#diagnostics) lists them under `quarantined`.
- The [Modbus Scanner](../support/modbus_scanner/README.md) shows in seconds
  which registers the device actually serves.

If the device genuinely never serves the register, remove the entity from the
device file (for a bundled file, please report it). Unused addresses the
device refuses *between* entities belong in the file's
[`bad_addresses`](device_files.md#read-planning-and-polling).

## Everything is unavailable

The device did not answer at all: a wrong Modbus device ID, or the gateway is
up while its RS-485 side is down. The integration logs once when a device
becomes unreachable and once when it recovers, and keeps retrying on its own —
see [when the device is offline](how_it_works.md#when-the-device-is-offline).

## Values are wrong

- **Nonsense numbers** — usually byte order. In the device file, try
  `swap: word`, `swap: byte` or `swap: word_byte`.
- **Off by a factor of 10 or 100** — check `multiplier`.
- **A setting snaps back after you change it** — the device may apply writes
  slowly; `confirm_delay` in the device file delays the confirming read.

For a bundled file, please report what you find. The
[device file reference](device_files.md#modbus-keys-per-entity) explains each
key.

## An entity I expect is missing

It is probably in an entity group that is switched off. Open the device's
companion *Configuration* device and enable the group — see
[entity groups](entity_groups.md).

## Diagnostics

On the device page, open the three-dot menu and choose **Download
diagnostics**. The file contains the parsed device definition, the poll
planning state (including quarantined registers and failure counts per entity)
and the current values. The host is redacted; the values are not, so look the
file over before posting it publicly.

## Debug logging

```yaml
logger:
  logs:
    custom_components.modbus_connect: debug
    pymodbus: info
```

## Known limitations

- **Serial adapters must be visible to Home Assistant.** For a direct serial
  connection the adapter has to show up as a device on the machine running
  Home Assistant. In containers, map it in, and prefer the stable
  `/dev/serial/by-id/…` paths. A networked RS-485 bridge works either as a
  Modbus TCP gateway or in transparent mode with *Modbus RTU over TCP*.
- **No discovery.** Modbus has no discovery protocol; the address has to be
  entered by hand.
- **One device per entry.** A gateway serving several Modbus device IDs needs
  one entry per device. They share the connection automatically.
- **At most 125 registers per read.** That is the Modbus protocol limit; a
  device file's `max_register_read` can only lower it.
- **`flags` entities are read-only.** A bit field cannot be written back as a
  whole. A device file uses `mask` with `read_modify_write` to write single
  fields.
- **Writes use the same conversions as reads**, so a value that cannot be
  encoded (one that is not in the entity's `map`, for example) is rejected
  instead of written.
