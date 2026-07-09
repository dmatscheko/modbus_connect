<picture>
  <source media="(prefers-color-scheme: dark)" srcset="custom_components/modbus_connect/brand/dark_logo@2x.png">
  <img alt="Modbus Connect" src="custom_components/modbus_connect/brand/logo@2x.png" width="480">
</picture>

A Home Assistant custom integration for Modbus devices behind local TCP
gateways — a ground-up rewrite of
[modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway) that
also draws on
[homeassistant-solax-modbus](https://github.com/wills106/homeassistant-solax-modbus),
built around four ideas:

1. **Block reads.** Instead of one Modbus round trip per entity, each poll
   merges everything into as few reads as possible: overlapping and adjacent
   registers combine, small unused holes are bridged (cheaper to read than to
   ask twice), and blocks respect the device's `max_register_read` and the
   protocol limit of 125 registers. Real device files: an Eastron SDM630 drops
   from 85 transactions per poll to 7; a Pichler LG350 from 129 to 5. Registers
   the device chokes on are learned from failed reads and routed around; stubborn
   ones can be declared up front (`bad_addresses`, `split_before`).
2. **Home Assistant is not shadowed.** Every entity has an `ha:` block that is
   passed to the real per-platform `EntityDescription` and validated against
   it — any entity feature HA supports (today or in a future release) can be
   set there, and typos fail loudly with the file, entity, and valid choices
   in the message.
3. **Symmetric conversions.** Whatever the integration can decode it can also
   encode for writing (`multiplier`/`offset`, `map`, `sum_scale`, masked bit
   fields via read-modify-write). Only `flags` is inherently read-only.
4. **Templates, not code.** Derived values are declared as Jinja over the
   device's register values and re-rendered every poll, and the same engine
   drives writes. Device quirks become a few lines of YAML, not a plugin.

Failed bridged blocks fall back to unbridged reads automatically, and
addresses a device refuses to serve are remembered and never bridged again.
Offline devices back off exponentially (up to 5 min) instead of hammering the
gateway. One failing entity does not take down the rest; it just becomes
unavailable — and a register that keeps failing while the device answers
everything else is quarantined out of the read plan and re-probed every
10 minutes, so a single bad address never costs permanent traffic.

Typical use cases: energy meters (Eastron SDM), solar inverters and hybrid
storage (Growatt), heat pumps (Dimplex, Husdata gateways), ventilation units
(Pichler, Salda), motor drives (Schneider Altivar), relay boards (Waveshare,
Finder) — or any other device that speaks Modbus TCP, directly or through an
RS-485 gateway.

## Installation

### HACS (recommended)

1. In HACS, choose **Custom repositories** in the three-dot menu, add
   `https://github.com/dmatscheko/modbus_connect` with type **Integration**
   (or click
   [![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dmatscheko&repository=modbus_connect&category=integration)).
2. Install **Modbus Connect** and restart Home Assistant.

### Manual

Copy `custom_components/modbus_connect/` into
`<ha_config>/custom_components/` and restart Home Assistant.

It can be installed side by side with `modbus_local_gateway`; entities are
independent.

## Configuration

Add the **Modbus Connect** integration in **Settings → Devices & services**
(or click
[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=modbus_connect)).
The connection is tested before anything is created. Add the integration once
per Modbus device — several devices can share one gateway.

**Step 1 — device:**

| Setting | Meaning | Default |
| --- | --- | --- |
| Device definition | The YAML file describing the device's registers | — |
| Device name | Friendly name of the device and its config entry | manufacturer + model |

**Step 2 — connection:**

| Setting | Meaning | Default |
| --- | --- | --- |
| Host | Hostname or IP of the Modbus TCP gateway | — |
| Port | TCP port of the gateway | `502` |
| Modbus device ID | Unit/slave ID of the device behind the gateway (0–255) | the device file's `modbus_id`, else `1` |
| Entity ID prefix | Start of all entity IDs of this device: `sensor.<prefix>_<key>` | the device file's `prefix`, else the device name |

The Modbus device ID and the prefix are prefilled from the chosen device
file, so devices whose factory default ID is not `1` work without looking it
up. Clear the prefix to let Home Assistant derive entity IDs from the device
name instead. Entity IDs are only assigned when an entity is first created —
changing the prefix later does not rename existing entities.

**Options** (gear icon on the integration entry): the *minimum* poll interval
in seconds (1–86400) — a floor. The device file and individual entities set the
actual per-entity cadences; this only raises them, it never polls faster.

**Reconfigure** (three-dot menu → *Reconfigure*): change the device file,
name, gateway address, device ID, or prefix without removing the entry.

## Device files

Every device is described by one YAML file — a bundled one from the table
below, or your own in `<ha_config>/modbus_connect/` (your files survive
updates and override built-in files with the same name; invalid files are
reported in the log with the entity and reason and skipped).

A few lines per entity are enough:

```yaml
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

The complete format — register types and conversions, writable entities,
composite `template:` entities (climate, fan, cover, …), entity groups, and
read-planning hints — is documented in the
[device file reference](docs/device_files.md).

## Bundled device files

Community-contributed definitions ship with the integration (most converted
from `modbus_local_gateway`); pull requests with new files are welcome. Any
Modbus TCP device not listed here works too — write a device file for it.

| Manufacturer | Model | File |
| --- | --- | --- |
| Dimplex | Sole/Wasser-Wärmepumpe SI 11TU | `Dimplex-SI-11TU.yaml` |
| Eastron | SDM-230 | `SDM230.yaml` |
| Eastron | SDM-630 | `SDM630.yaml` |
| ebyte | ME31-AXAX404 | `ME31-AXAX404.yaml` |
| Finder | 7M.24 | `7M_24.yaml` |
| Finder | 7M.38 | `7M_38.yaml` |
| Fröling | BWP300 PV | `Fröling_BWP300PV.yaml` |
| Growatt | MIC 2500TL-X | `MIC-2500TL-X.yaml` |
| Growatt | MIN 6000TL-XH | `MIN-6000TL-XH.yaml` |
| Growatt | MOD 6000TL-X | `MOD-6000TL-X.yaml` |
| Growatt | MOD 10KTL3-XH | `MOD-10KTL3-XH.yaml` |
| Growatt | SPH3600TL BL_UP | `SPH-3600TL-BL_UP.yaml` |
| Husdata | H60 | `Husdata_H60.yaml` |
| Pichler | Lüftungsgerät LG 150 – LG 250 | `Pichler-LG150-LG250.yaml` |
| Pichler | Lüftungsgerät LG 350 – LG 450 | `Pichler-LG350-LG450.yaml` |
| Salda | RIS / RIRS (MCB) | `Salda_RIS_MCB.yaml` |
| Schneider Electric | Altivar ATV312 | `Schneider_ATV312.yaml` |
| Schneider Electric | Altivar ATV312 Expert | `Schneider_ATV312_expert.yaml` |
| SolaX Power | X3-Hybrid G4 | `Solax_X3_Hybrid_G4.yaml` |
| SolaX Power | X3-HAC (11 kW EV charger) | `Solax_X3_HAC.yaml` |
| Varmann | Qtherm | `Varmann Qtherm.yaml` |
| Waveshare | Modbus POE ETH Relay 30CH | `Waveshare_30_POE.yaml` |
| Waveshare | Modbus RTU Relay (D) | `Waveshare_RTU_Relay_D.yaml` |

## Entity groups

Big devices expose far more settings and sensors than most people want, so a
device file can tag its entities into named groups — `basic`, `advanced`,
`all`, … (how, is in the [device file
reference](docs/device_files.md#entity-groups)). For every group in the file,
the integration adds one **Enable _group_ entities** switch, so whole sets can
be turned on and off from the device page; an entity shows while any of its
groups is enabled. **`basic` is special**: it is always enabled and gets no
switch — the everyday baseline can never be hidden, so you cannot lock
yourself out by disabling the group everything lives in.

The group switches and the *Reads per refresh* diagnostic don't clutter the
device itself: they live on a companion **_device name_ Configuration** service
device on the same config entry. The two devices are cross-linked — each shows
the other as its "Connected via" device, so you can jump between them from
either info card.

Toggling a switch reloads the entry and **rebuilds the entity set**. Hidden
entities are not merely disabled — they stop being provided, so Home Assistant
greys them out as "no longer provided", *keeps their registry row* (your renames,
areas, and enabled/disabled state), and restores them the moment the group is
turned back on. Hidden entities also drop out of the Modbus read plan. The
bundled SolaX Hybrid file, for instance, goes from 232 entities / 210 register
reads on *all* down to 27 / 29 on *basic*.

If you'd rather be rid of the greyed-out leftovers, the Configuration device has
a **Remove hidden entities** button: it deletes every registry entry the current
group selection no longer provides (including stale ones from an earlier device
file), without touching anything that is provided — customizations on live
entities, even manually disabled ones, are safe. It's a deliberate action
precisely because those rows hold your renames and settings; nothing is ever
deleted just by flipping a group switch.

## How data is updated

The integration polls. Each cycle collects every entity that is due, plans
the minimal set of block reads (see the top of this page), executes them over
one shared TCP connection per gateway, and decodes all values from the
result. The device file sets each entity's poll cadence; the config-entry
option is only a *floor* that slows polling down, never speeds it up (the
exact precedence is in the [device file
reference](docs/device_files.md#read-planning-and-polling)). Writes are
confirmed by reading the register back immediately.

Each device also gets a **Reads per refresh** diagnostic sensor (on its
*Configuration* companion device) showing how many Modbus block reads a full
refresh issues. Thanks to block merging this is usually far below the entity
count — its `read_entities` attribute is the total that poll, so the gap is the
merge win made visible. It reports the stable full-refresh figure (it moves only
when the read plan does), so it costs the recorder almost nothing; the live
per-cycle read and poll counts are in *Download diagnostics* instead.

Read health lives next to it: a **Read failures** problem indicator that turns
on while any read failed in the last 5 minutes (its attributes carry the count
in that window and the running total), and a **Failed reads** counter of failed
read transactions since the last reload — chart it or alert on its rate. Both
count unrecovered failures only: a bridged block that fails once and teaches the
planner a dead filler address is planning, not a device problem. A healthy
device writes neither entity to the recorder.

A register that keeps failing while the device answers everything else — the
signature of a wrong address in a device file — is **quarantined**: after
three consecutive misses, or immediately when the device reports the address
as illegal, the entity goes unavailable and its registers leave the read plan.
A standalone probe every 10 minutes (and any reload) lifts the quarantine the
moment the device serves the register again. The quarantine is announced as a
warning in the log naming the entity and its address.

To find *which* register keeps failing: *Download diagnostics* lists
`quarantined` and `failed_reads_by_key` (failure counts per entity, worst
first), and with debug logging enabled (device page → *Enable debug logging*,
or logger `custom_components.modbus_connect`) every unrecovered failure logs
the address range and the entities it covers. A register the device genuinely
never serves is best removed from the config or declared in
[`bad_addresses`](docs/device_files.md#read-planning-and-polling).

## Automation examples

Entities behave like any other Home Assistant entities:

```yaml
automation:
  - alias: Boost ventilation while cooking
    triggers:
      - trigger: state
        entity_id: binary_sensor.kitchen_hood_running
        to: "on"
    actions:
      - action: fan.set_percentage
        target:
          entity_id: fan.pichler_lg350_ventilation
        data:
          percentage: 75

  - alias: Warn on inverter fault
    triggers:
      - trigger: state
        entity_id: sensor.growatt_mod_6000tl_x_fault_flags
    conditions: "{{ trigger.to_state.state not in ('', 'unknown', 'unavailable') }}"
    actions:
      - action: notify.mobile_app_phone
        data:
          message: "Inverter fault: {{ trigger.to_state.state }}"
```

## Known limitations

- **Modbus TCP only.** Serial (RTU) devices need an RS-485↔TCP gateway such
  as a Waveshare/Elfin/USR box; the integration does not open serial ports.
- **No discovery.** Modbus has no discovery protocol; the gateway address
  must be entered manually.
- **Reads are capped at 125 registers** per transaction by the Modbus
  protocol; `max_register_read` can only lower that.
- **`flags` entities are read-only** — a bit field cannot be written back as
  a whole. Use `mask` with `read_modify_write` to write single fields.
- **Writes go through the same conversions as reads**, so a value that
  cannot be encoded (e.g. not in the `map`) is rejected instead of written.
- **One device per config entry.** A gateway serving several slave IDs needs
  one entry per device (they share the TCP connection automatically).

## Troubleshooting

- **"Failed to connect" in the config flow** — check host/port, and that
  nothing else holds the gateway's only TCP slot; many cheap RS-485 gateways
  allow exactly one client.
- **Some entities are unavailable** — the device rejected their addresses
  (wrong device file, or the register only exists on other firmware). The
  log lists every address the device refused. Those addresses are excluded
  from gap bridging automatically.
- **Everything is unavailable** — the device did not answer at all: wrong
  slave ID, or the gateway is up while the RS-485 side is down. The
  integration logs once when a device becomes unreachable and once when it
  recovers, and retries with exponential backoff (up to 5 min).
- **Wrong values** — usually byte order: try `swap: word`, `byte`, or
  `word_byte`, and check `multiplier`.
- **Diagnostics**: the device page offers *Download diagnostics* with the
  parsed device definition, poll planning state, and current values (host
  redacted).
- **Debug logging**:

  ```yaml
  logger:
    logs:
      custom_components.modbus_connect: debug
      pymodbus: info
  ```

## Removal

Remove the integration entry in **Settings → Devices & services** (this
deletes its entities and device), then remove **Modbus Connect** in HACS (or
delete `custom_components/modbus_connect/` manually) and restart Home
Assistant. Your own device files in `<ha_config>/modbus_connect/` are never
deleted automatically.

## Quality

Custom integrations cannot carry an official quality scale rating (the
manifest says `custom`), but the code follows the
[integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
up to and including the **Platinum** rules — connection test before setup,
reconfigure flow, translations (English and German), translated exceptions,
diagnostics, parallel-update limits, strict typing, async I/O throughout, and
98% test coverage. [`quality_scale.yaml`](custom_components/modbus_connect/quality_scale.yaml)
documents every rule, including the exemptions (Modbus has no discovery, no
authentication, and no fixed entity set to translate).

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/python -m pytest tests/ --cov=custom_components.modbus_connect
.venv/bin/ruff check custom_components tests converter support
.venv/bin/mypy custom_components/modbus_connect   # strict, see pyproject.toml
```

Layout: `models.py` (plain dataclasses), `codec.py` (registers ↔ values,
pure), `planner.py` (block planning, pure), `client.py` (pymodbus wrapper),
`schema.py` (YAML validation), `coordinator.py` (polling, cache, backoff,
writes), `entity.py` + thin platform modules including template-driven
`climate.py`. The pure modules have no Home Assistant imports and are tested
standalone; `tests/test_e2e_server.py` proves the transaction counts against
a real TCP server. The device-file YAML format is documented in
[docs/device_files.md](docs/device_files.md).

Brand assets live in `support/` (SVG sources and `build_brand.py` to
regenerate them and the PNGs in `custom_components/modbus_connect/brand/`,
which Home Assistant ≥ 2026.3 serves locally), next to
`support/modbus_cli.py` — a standalone Modbus debugging CLI (probe, read
with decoded views, write, register scan; see its `--help`).

Releases are cut from the GitHub **Actions** tab: run the *Release* workflow
and enter the version (e.g. `0.3.0`). It re-runs the full gate (ruff, mypy,
tests), bumps `manifest.json`/`pyproject.toml` when the version is new, tags
`vX.Y.Z`, and publishes a GitHub release with generated notes — the version
HACS then offers to users.
