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
unavailable.

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

## Your own device files

Put YAML files in `<ha_config>/modbus_connect/` — they survive updates and
override built-in files with the same name. Invalid files are reported in the
log with the entity and reason and skipped.

## Device file format

Entities are grouped by Modbus table, exactly like the datasheet: `holding:`
(read/write registers), `input:` (read-only registers), `coil:` (read/write
bits), `discrete:` (read-only bits). The platform is free within what the
table allows — for example, a *holding* register can deliberately be exposed
as a read-only `sensor` when changing it would be dangerous.

Several entities may read the same registers (e.g. a raw value and a scaled
twin, or single bits of a status word) — each register is still read only
once per poll.

```yaml
device:
  manufacturer: Eastron
  model: SDM630
  max_register_read: 100   # max registers per read request (default 8, cap 125)
  max_read_gap: 8          # bridge unused holes up to this many registers (default 8)
  bad_addresses:           # never read or bridge across these (optional), by table —
    holding: [0x99]        #   registers the device answers with an error
  split_before:            # force a fresh read block to start at these (optional),
    holding: [0x30, 400]   #   by table — for devices that dislike spanning them
  scan_interval: 30        # default poll interval in seconds; entities without
                           #   their own inherit this (optional, default 30)
  min_scan_interval: 10    # floor: never poll faster than this (optional; unset
                           #   imposes no floor). The options dialog can only raise it
  modbus_id: 1             # factory-default Modbus device ID (optional);
                           #   prefills the config flow for this device
  prefix: sdm630           # default entity-id prefix (optional); the config
                           #   flow prefills it with this, else the device name
  sw_version: "DSP {{ dsp }} ARM {{ arm }}"  # firmware / hardware / serial for the
  hw_version: "{{ hardware_gen }}"           #   device page (all optional); each is a
  serial_number: "{{ serial }}"             #   template over register values (below)

input:
  phase_1_voltage:
    address: 0x0000        # register/coil address (decimal or hex)
    type: float32          # uint16 (default) | int16 | uint32 | int32 | uint64 |
                           # int64 | float16 | float32 | float64 | uint8 | int8 |
                           # bit (alias int1) | string | time
    ha:
      platform: sensor     # sensor | binary_sensor | number | select | switch |
                           # text | time | button
      name: Phase 1 voltage
      device_class: voltage
      state_class: measurement
      unit_of_measurement: V
      precision: 1

holding:
  operating_mode:
    address: 5015
    map: {0: "Off", 1: "Auto", 2: "Party"}
    duplicate_as_sensor: true
    ha:
      platform: select
      name: Operating mode
      entity_category: config

  reset_alarm:
    address: 5020
    write_value: 1
    ha:
      platform: button
      name: Reset alarm

coil:
  pump:
    address: 3
    ha:
      platform: switch
      name: Circulation pump
```

`sw_version`, `hw_version`, and `serial_number` fill the fields of the same name
on the device page. Each is a Jinja template over the device's register values —
declare the registers you reference (usually as `internal:` entities, since they
need no entity of their own) and format them with the usual filters, e.g.
`sw_version: "DSP {{ dsp | round(2) }} ARM {{ arm | round(2) }}"`. They are
rendered once from the first read.

### Modbus keys (per entity)

| Key | Meaning |
| --- | --- |
| `address` | Start address (0–65535, hex `0x…` works) |
| `type` | Value type; determines register count. `string` needs `count`. Sub-word types (`uint8`/`int8` = low byte, `bit` = least significant bit) read one register. `time` is HH:MM on a `time` platform — one register (high byte hour, low byte minute; add `swap: byte` for the reverse), or `count: 2` for the two-register form (first register hour, second minute). Bit tables are implicitly `bool` |
| `count` | Register count — only for `string` (2 characters per register) |
| `swap` | `byte`, `word`, or `word_byte` for little-endian devices |
| `sum_scale` | List of per-element weights: `value = Σ element[i] · scale[i]`, where each element has the entity's `type` (default `uint16` — one register per weight). Example `[1, 10000, 100000000]` for a counter spread over 3 registers. With `type: uint8` each register holds two elements (low byte first — combine with `swap: byte` for devices that pack high byte first), so the same weights cover 1.5 registers (2 are read); with `type: bit` each register holds sixteen (LSB first). Writable when the weights are positive integers and the type is an unsigned integer |
| `mask` | Extract bits: `value = (raw & mask) >> trailing_zeros(mask)`. Replaces the old `bits`/`shift_bits` pair |
| `multiplier` / `offset` | `value = raw · multiplier + offset` (inverted on write) |
| `map` | `{register value: label}` — enums; used as the options of a `select` |
| `flags` | `{bit number (0-indexed): name}` — sensor shows the set flags, read-only |
| `on` / `off` | Values meaning on/off for `switch`/`binary_sensor` (defaults: 1/0, true/false) |
| `write_value` | What a `button` writes when pressed. A fixed number/boolean **or a single Jinja template** (`"{{ … }}"`) goes through the entity's codec, honouring `type`/`map`/`multiplier`/`count` (so int32, float, mapped labels, and strings all work). A **list** of numbers/templates instead writes each item as one raw 16-bit register in a single FC16 transaction — for register blocks like an RTC sync: `["{{ now().second }}", "{{ now().minute }}", …]`. Templates render over the current values with the usual HA functions (`now()`, `utcnow()`, …) |
| `read_register` | Take the current value from elsewhere instead of this entity's own register — a Jinja template like the `template:` section (e.g. `"{{ other_key }}"`). For settings a device echoes on a different register (or table) than it accepts writes on: this entity writes to its own `address`/table, while the referenced entity — often `internal:`, with its own `type`/`mask`/`multiplier`, and free to live in `input:`/`discrete:` — supplies the read-back |
| `read_modify_write` | Allow writing a `mask`ed field by merging into the current register |
| `static_value` | Marks a write-only command register: never read it — the entity shows this value until written, then optimistically its last written value (an option label for a `select`, a number for a `number`). For "direct control" registers that echo nothing useful, or share an address with an unrelated read |
| `optimistic_default` | Read the register as usual, but fall back to this value when it decodes to nothing (undecodable / out of range) — keeps a writable control usable instead of unavailable. Mutually exclusive with `static_value`; neither combines with `read_register` |
| `write_multiple` | Force FC16 (write-multiple) for the write, even for a single register — some devices reject FC6 on certain registers (e.g. SolaX `WRITE_MULTISINGLE`) |
| `rectify_time` | `time` entities only: show an out-of-range time (e.g. `24:00`, an end-of-day stop time HA's `time` type cannot represent) as `23:59` instead of dropping the entity — so the slot stays usable |
| `max_change` | Reject changes larger than this between two polls (spike filter) |
| `never_resets` | Ignore decreasing values (for `total_increasing` counters) |
| `scan_interval` | Per-entity poll interval in seconds, overriding the device default. Still raised to `min_scan_interval` if that is longer |
| `duplicate_as_sensor` | Also create a read-only sensor twin of this writable entity, so its history lands in the recorder/long-term statistics |
| `internal` | Poll and decode this register for the `template:` section only — **no Home Assistant entity is created** (so it has no `ha:` block). Internal entities can still be write targets of template actions. If you want the entity to exist but stay out of sight, use `ha.enabled_by_default: false` instead |

### The `ha:` block

`platform` selects the entity type; every other key is a field of that
platform's `EntityDescription`. Friendly aliases: `unit_of_measurement`/`unit`
→ `native_unit_of_measurement`, `min`/`max`/`step` → `native_min_value`/`…`,
`precision` → `suggested_display_precision`, `enabled_by_default` →
`entity_registry_enabled_default`. Enum fields (`device_class`,
`state_class`, `entity_category`, number/text `mode`) are validated with the
full list of valid values in the error message.

## The `template:` section

Composite entities built from the device's values with real Home Assistant
Jinja templates. Every entity key of the device file is available as a plain
variable (and via the `values` dict); all normal HA template functions work
too. Templates re-render on every device poll.

```yaml
holding:
  hot_water_target:      # only used by the climate entity below
    address: 5033
    multiplier: 0.1
    internal: true       # polled, decoded, writable — but no HA entity
  operating_mode:
    address: 5015
    map: {0: "Off", 1: "Auto"}
    internal: true

template:
  cop:                                  # a computed sensor
    state: "{{ (heat_output / power_input) | round(2) if power_input else none }}"
    ha:
      platform: sensor
      name: COP
      precision: 2

  water_heater:                         # a climate entity from Modbus parts
    ha:
      platform: climate
      name: Hot water
    current_temperature: "{{ hot_water_temperature }}"
    target_temperature: "{{ hot_water_target }}"
    hvac_mode: "{{ 'heat' if operating_mode == 'Auto' else 'off' }}"
    hvac_action: "{{ 'heating' if compressor_running else 'idle' }}"
    min_temp: 30
    max_temp: 60
    temp_step: 0.5
    set_temperature: {entity: hot_water_target}
    set_hvac_mode:
      entity: operating_mode
      map: {heat: "Auto", "off": "Off"}   # hvac mode -> value written
```

Write actions (`turn_on`, `set_temperature`, …) target one of the device's
entities by key — through the same codec as everything else, so multipliers,
offsets, and select maps apply. Targets must live in a writable table
(`holding:`/`coil:`) and may be `internal`. Actions come in three kinds:
fixed (`{entity: x, value: 1}` — on/off/open/close/stop), value-carrying
(`{entity: x}` — the UI value is written), and mapped
(`{entity: x, map: {ui value: written value}}`).

Instead of a single `entity`, any action may choose its target at write time
with `by`/`cases`: the `by` template is rendered and its value selects a case,
each case being an ordinary target (with its own optional `value`/`map`). Every
case is validated and codec-routed like a normal target; a rendered value with
no matching case raises an error instead of writing to the wrong register. This
lets one control write to different registers depending on another value — e.g.
a thermostat whose active setpoint follows a regulation-type selector:

```yaml
set_temperature:
  by: "{{ regulation_mode }}"          # rendered on each write; its value picks a case
  cases:
    supply:  {entity: supply_setpoint}
    room:    {entity: room_setpoint}
    exhaust: {entity: exhaust_setpoint}
```

The read side needs no special construct — a template already sees every value,
so `current_temperature`/`target_temperature` can switch inputs with a plain
`{{ {'supply': t_supply, 'room': t_room}[regulation_mode] }}`.

| Template platform | Templates | Actions | Statics |
| --- | --- | --- | --- |
| `sensor`, `binary_sensor` | `state` | — | — |
| `switch` | `state` | `turn_on`, `turn_off` (fixed) | — |
| `number` | `state` | `set_value` | `ha.min`/`ha.max` required |
| `select` | `state` | `select_option` (mapped) | `options` (or derived from the action map / the target's `map`) |
| `light` | `state`, `brightness` (0–255) | `turn_on`, `turn_off` (fixed), `set_brightness` | — |
| `fan` | `state`, `percentage` (0–100), `preset_mode` | `turn_on`, `turn_off` (fixed), `set_percentage`, `set_preset_mode` (mapped) | `preset_modes` (or derived from the map) |
| `cover` | `is_closed` and/or `position` (0–100) | `open_cover`, `close_cover`, `stop_cover` (fixed), `set_position` | — |
| `climate` | `current_temperature`, `target_temperature`, `hvac_mode`, `hvac_action` | `set_temperature`, `set_hvac_mode` (mapped) | `min_temp`, `max_temp`, `temp_step`, `temperature_unit`, `hvac_modes` (or derived from the map) |

A ventilation unit, for example:

```yaml
template:
  ventilation:
    ha: {platform: fan, name: Ventilation}
    state: "{{ fan_stage > 0 }}"
    percentage: "{{ fan_stage * 25 }}"          # stages 0-4
    turn_on: {entity: fan_stage, value: 2}
    turn_off: {entity: fan_stage, value: 0}
    set_percentage: {entity: fan_stage_percent}  # or an internal scaled twin
```

Why not pass templates through to HA's template integration? Its platform
setup is internal API (and core has no template *climate*), its entities would
not belong to this device or unload with it, and you would have to reference
global entity ids instead of the device's keys. The Jinja engine used here
*is* Home Assistant's own — only the thin entity glue is local.

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

## How data is updated

The integration polls. Each cycle collects every entity that is due, plans
the minimal set of block reads (see the top of this page), executes them over
one shared TCP connection per gateway, and decodes all values from the
result. The effective interval per entity is `max(floor, cadence)`: the *cadence*
is the entity's `scan_interval`, else the device file's `scan_interval`, else
30 s; the *floor* is the larger of the config-entry option and the device file's
`min_scan_interval` (unset, it imposes no floor — it defaults to the config's
fastest cadence). So `scan_interval` sets the actual rate, while
`min_scan_interval` and the option only ever slow polling down, never below the
floor. Writes are confirmed by reading the register back immediately.

Each device also gets a **Reads per refresh** diagnostic sensor (in the device
page's *Diagnostic* section) showing how many Modbus reads the last poll
actually issued. Thanks to block merging this is usually far below the entity
count — its `polled_entities` and `read_entities` attributes show how many
entities that refresh covered versus the total that poll, so the gap is the
merge win made visible.

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
.venv/bin/ruff check custom_components tests converter
.venv/bin/mypy custom_components/modbus_connect   # strict, see pyproject.toml
```

Layout: `models.py` (plain dataclasses), `codec.py` (registers ↔ values,
pure), `planner.py` (block planning, pure), `client.py` (pymodbus wrapper),
`schema.py` (YAML validation), `coordinator.py` (polling, cache, backoff,
writes), `entity.py` + thin platform modules including template-driven
`climate.py`. The pure modules have no Home Assistant imports and are tested
standalone; `tests/test_e2e_server.py` proves the transaction counts against
a real TCP server.

Brand assets live in `support/` (SVG sources and `build_brand.py` to
regenerate them and the PNGs in `custom_components/modbus_connect/brand/`,
which Home Assistant ≥ 2026.3 serves locally).
