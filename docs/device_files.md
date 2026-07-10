# Device file reference

Every device Modbus Connect talks to is described by one YAML file. Bundled
files ship with the integration (see the [README's device
table](../README.md#bundled-device-files)); your own go in
`<ha_config>/modbus_connect/` — they survive updates and override built-in
files with the same name. Invalid files are reported in the log with the
entity and reason and skipped.

This page is the complete format reference for writing such a file:
the [`device:` section](#the-device-section), [read planning and
polling](#read-planning-and-polling), the per-entity [Modbus
keys](#modbus-keys-per-entity) and [`ha:` block](#the-ha-block), [entity
groups](#entity-groups), and the [`template:` section](#the-template-section)
for composite entities.

## Layout

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
  default_groups: [basic]  # which entity groups start enabled (optional; see below).
                           #   Unset shows every group — i.e. all entities.
                           #   'basic' is always enabled either way

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

## The `device:` section

The commented example above covers the keys. `sw_version`, `hw_version`, and
`serial_number` fill the fields of the same name on the device page. Each is a
Jinja template over the device's register values — declare the registers you
reference (usually as `internal:` entities, since they need no entity of their
own) and format them with the usual filters, e.g.
`sw_version: "DSP {{ dsp | round(2) }} ARM {{ arm | round(2) }}"`. They are
rendered once from the first read.

## Read planning and polling

Each poll cycle collects every entity that is due and merges their registers
into as few block reads as possible: overlapping and adjacent spans combine,
small unused holes up to `max_read_gap` are bridged (reading a few unneeded
registers is cheaper than a second round trip), and no block exceeds
`max_register_read` or the protocol limit of 125 registers.

A failed bridged block falls back to unbridged reads automatically, filler
addresses the device refuses to serve are learned as holes and never bridged
again, and a failed retry covering several entities is read once more entity
by entity, so one dead register cannot take its readable neighbours down. A
register that keeps failing while the device answers everything else (three
consecutive polls, or one explicit illegal-address answer) is quarantined: its
entity goes unavailable, its registers leave the read plan, and a standalone
probe every 10 minutes lifts the quarantine as soon as the device serves it
again — a wrong `address:` costs a warning and a probe, not permanent traffic.
Two device keys steer the planner up front when a device is known to be picky:

- `bad_addresses:` — registers the device answers with an error, per table;
  never read and never bridged across.
- `split_before:` — a fresh read block must start at these addresses, per
  table; for devices that fail any read *spanning* them.

The effective poll interval per entity is `max(floor, cadence)`: the *cadence*
is the entity's `scan_interval`, else the device file's `scan_interval`, else
30 s; the *floor* is the larger of the config-entry option and the device
file's `min_scan_interval` (unset, it imposes no floor — it defaults to the
config's fastest cadence). So `scan_interval` sets the actual rate, while
`min_scan_interval` and the option only ever slow polling down. Writes are
confirmed by reading the register back immediately.

To watch the plan at work: *Download diagnostics* shows the parsed definition,
the planning state (including learned holes and quarantined registers), and
per-entity failure counts (`failed_reads_by_key`, worst first) — see the
README's [read health](../README.md#how-data-is-updated) section for the
entities that surface failures on the device page.

## Modbus keys (per entity)

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
| `on_value` / `off_value` | Values meaning on/off for `switch`/`binary_sensor` (defaults: 1/0, true/false). Reading: `on_value` matches on; with no `off_value` anything else is off, with one, other values are unknown |
| `write_value` | What a `button` writes when pressed. A fixed number/boolean **or a single Jinja template** (`"{{ … }}"`) goes through the entity's codec, honouring `type`/`map`/`multiplier`/`count` (so int32, float, mapped labels, and strings all work). A **list** of numbers/templates instead writes each item as one raw 16-bit register in a single FC16 transaction — for register blocks like an RTC sync: `["{{ now().second }}", "{{ now().minute }}", …]`. Templates render over the current values with the usual HA functions (`now()`, `utcnow()`, …) |
| `read_register` | Take the current value from elsewhere instead of this entity's own register — a Jinja template like the `template:` section (e.g. `"{{ other_key }}"`). For settings a device echoes on a different register (or table) than it accepts writes on: this entity writes to its own `address`/table, while the referenced entity — often `internal:`, with its own `type`/`mask`/`multiplier`, and free to live in `input:`/`discrete:` — supplies the read-back. A plain single-key reference passes the source value through unchanged (a `time`-typed read-back stays a time-of-day); anything more is rendered as a template and yields text/numbers |
| `read_modify_write` | Allow writing a `mask`ed field by merging into the current register |
| `static_value` | Marks a write-only command register: never read it — the entity shows this value until written, then optimistically its last written value (an option label for a `select`, a number for a `number`). For "direct control" registers that echo nothing useful, or share an address with an unrelated read |
| `optimistic_default` | Read the register as usual, but fall back to this value when it decodes to nothing (undecodable / out of range) — keeps a writable control usable instead of unavailable. Mutually exclusive with `static_value`; neither combines with `read_register` |
| `write_multiple` | Force FC16 (write-multiple) for the write, even for a single register — some devices reject FC6 on certain registers (e.g. SolaX `WRITE_MULTISINGLE`) |
| `rectify_time` | `time`-typed entities only (including `internal:` time read-backs): show an out-of-range time (e.g. `24:00`, an end-of-day stop time HA's `time` type cannot represent) as `23:59` instead of dropping the value — so the slot stays usable |
| `max_change` | Reject changes larger than this between two polls (spike filter) |
| `never_resets` | Ignore decreasing values (for `total_increasing` counters) |
| `scan_interval` | Per-entity poll interval in seconds, overriding the device default. Still raised to `min_scan_interval` if that is longer |
| `duplicate_as_sensor` | Also create a read-only sensor twin of this writable entity, so its history lands in the recorder/long-term statistics |
| `internal` | Poll and decode this register for the `template:` section only — **no Home Assistant entity is created** (so it has no `ha:` block). Internal entities can still be write targets of template actions. If you want the entity to exist but stay out of sight, use `ha.enabled_by_default: false` instead |
| `groups` | Tag the entity (or `template:` entry) into named groups, e.g. `[basic]` or `[advanced]`. The entity is created — and its register polled — only while at least one of its groups is enabled (`basic` is always enabled). In a file that uses groups, an entity with no `groups` is shown only while the *Enable all entities* switch bypasses group handling. See [Entity groups](#entity-groups) |

## The `ha:` block

`platform` selects the entity type; every other key is a field of that
platform's `EntityDescription`. Friendly aliases: `unit_of_measurement`/`unit`
→ `native_unit_of_measurement`, `min`/`max`/`step` → `native_min_value`/`…`,
`precision` → `suggested_display_precision`, `enabled_by_default` →
`entity_registry_enabled_default`. Enum fields (`device_class`,
`state_class`, `entity_category`, number/text `mode`) are validated with the
full list of valid values in the error message.

## Entity groups

Big devices expose far more settings and sensors than most people want. Tag
entities (and `template:` entries) with `groups:` to let the user switch whole
sets on and off from the device page:

```yaml
device:
  default_groups: [basic]        # what a fresh install (and existing ones) start with
holding:
  battery_soc:
    address: 0
    groups: [basic]              # everyday view (always enabled)
  inverter_frequency:
    address: 10
    groups: [advanced]           # shown when the Advanced switch is on
  cell_voltage_16:
    address: 20                  # untagged: expert tier, shown by "Enable all entities"
```

An entity is shown when **any** of its groups is enabled. `default_groups`
picks which groups start enabled; leave it out and everything shows.

**`basic` is special**: it is always enabled and gets no switch. Tagging an
entity `groups: [basic]` means "part of the always-visible baseline" — it
keeps the entity out of the other groups without ever letting it be hidden, so
a user cannot lock themselves out by disabling the group everything lives in.

Besides the per-group switches there is one **Enable all entities** switch:
while it is on, group handling is bypassed entirely and every entity of the
file exists — an entity tagged into *no* group is exactly the "everything
else" tier behind that switch. (`all` is not a reserved name: a file may
declare a group called `all`, which behaves like any other named group.) The
switches only exist in files that use `groups:` at all; an untagged file
simply shows every entity, always.

Hidden entities also drop out of the Modbus read plan — though a shown
template, `read_register`, `write_value`, or action selector keeps its own
source registers polled even when those sources are hidden, so a visible value
never loses its inputs. How the switches, the companion *Configuration*
device, and the *Remove hidden entities* button behave for the user is covered
in the README's [Entity groups](../README.md#entity-groups) section.

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

## Validating and debugging a file

Schema errors are loud by design: an invalid file is skipped and the log names
the file, the entity, and the reason — enum fields even list every valid
value. Once a file loads, *Download diagnostics* on the device page shows the
parsed definition, the read-planning state, and the current values, and the
README's [troubleshooting](../README.md#troubleshooting) section covers wrong
values (byte order, multipliers) and unreachable registers.

To poke the device directly — before a file exists, or when a register
misbehaves — the repo ships a standalone CLI (needs only `pymodbus`):
`python3 support/modbus_cli.py --host <gateway> --help`. It can `probe` the
connection, `read` registers with every common decoding shown next to the raw
words (so the right `type`/`swap` can be read straight off), `write` via FC6,
FC16, or FC5, and `scan` an address range — the scan prints unreadable
registers and forced block boundaries as ready-to-paste `bad_addresses:` /
`split_before:` device keys. `--debug` logs every Modbus frame on the wire. Pull requests with
new device files are welcome — see the [bundled
files](../README.md#bundled-device-files).
