# Device file reference

Every device Modbus Connect talks to is described by one YAML file. This page
is the complete format reference. If you are writing your first file, start
with the step-by-step guide,
[writing a device file](writing_a_device_file.md), and come back here to look
things up.

Bundled files ship with the integration (see
[supported devices](supported_devices.md)). Your own go in
`<ha_config>/modbus_connect/`; they survive updates and override a bundled
file with the same name. An invalid file never loads silently — the setup
dialog and the log name the file, the entity and the reason.

**On this page**

- [Layout](#layout) — the shape of a file, with a commented example
- [The `device:` section](#the-device-section) — device-wide settings
- [Read planning and polling](#read-planning-and-polling) — block reads,
  failures, intervals, writes
- [Modbus keys (per entity)](#modbus-keys-per-entity) — address, type,
  conversions, write behaviour
- [The `ha:` block](#the-ha-block) — the Home Assistant side of an entity
- [Entity groups](#entity-groups) — letting users show and hide entities
- [The `template:` section](#the-template-section) — computed sensors and
  composite entities (climate, fan, cover, …)
- [Translations](#translations) — more than one language
- [Validating and debugging a file](#validating-and-debugging-a-file)

## Layout

A file has a `device:` section, up to four sections of register entities, and
optionally a `template:` and a `translations:` section.

Entities are sorted by Modbus table, exactly like the datasheet:

| Section | Modbus table | Access |
| --- | --- | --- |
| `holding:` | holding registers | read/write, 16-bit words |
| `input:` | input registers | read-only, 16-bit words |
| `coil:` | coils | read/write, single bits |
| `discrete:` | discrete inputs | read-only, single bits |

The platform is free within what the table allows — a *holding* register can
deliberately be exposed as a read-only `sensor` when changing it would be
dangerous.

Several entities may read the same registers (a raw value and a scaled twin,
or single bits of a status word). Each register is still read only once per
poll.

A commented example:

```yaml
device:
  manufacturer: Eastron
  model: SDM630
  max_register_read: 100   # max registers per read request (default 8; capped at the
                           #   protocol limit: 125 registers, 2000 coils/discrete inputs)
  max_read_gap: 8          # bridge unused holes up to this many registers (default 8)
  bad_addresses:           # never bridge a read across these (optional), by table —
    holding: [0x99]        #   unused registers the device answers with an error
  split_before:            # force a fresh read block to start at these (optional),
    holding: [0x30, 400]   #   by table — for devices that dislike spanning them
  scan_interval: 30        # default poll interval in seconds; entities without
                           #   their own inherit this (optional, default 30)
  min_scan_interval: 10    # floor: never poll faster than this (optional; unset
                           #   imposes no floor). The options dialog can only raise it
  timeout: 5               # seconds to wait per request (optional, default 2);
                           #   raise for slow devices and low baud rates
  retries: 2               # retransmits per unanswered request (optional, default 1)
  request_delay: 0.05      # seconds of enforced silence between any two requests
                           #   (optional, default 0) — for gateways that need the bus
                           #   quiet between frames; typical values 0.02–0.1
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
                           # text | time | button | valve
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

Only `manufacturer` and `model` are required.

| Key | Default | Meaning |
| --- | --- | --- |
| `manufacturer`, `model` | — | Shown on the device page and in the device picker |
| `max_register_read` | 8 | Most registers per read request; capped at the protocol limit (125 registers, 2000 coils/discrete inputs) |
| `max_read_gap` | 8 | Bridge unused holes of up to this many registers |
| `bad_addresses` | — | Per table: addresses the device answers with an error; no read is bridged across them |
| `split_before` | — | Per table: a fresh read block must start at these addresses |
| `scan_interval` | 30 | Default poll interval in seconds; entities without their own inherit it |
| `min_scan_interval` | — | Floor: never poll faster than this. Unset imposes no floor |
| `timeout` | 2 | Seconds to wait per request; raise for slow devices and low baud rates |
| `retries` | 1 | Retransmits per unanswered request |
| `request_delay` | 0 | Seconds of enforced silence between any two requests, for gateways that need the bus quiet between frames; typical values 0.02–0.1 |
| `modbus_id` | — | Factory-default Modbus device ID; prefills the setup dialog |
| `prefix` | — | Default entity-ID prefix; the setup dialog prefills it with this, else with the device name |
| `sw_version`, `hw_version`, `serial_number` | — | Templates that fill the fields of the same name on the device page |
| `default_groups` | — | Which [entity groups](#entity-groups) start enabled |
| `group_labels` | — | Display names for [entity groups](#entity-groups) |

**Connection tuning is shared.** `timeout`, `retries` and `request_delay` tune
the connection for slow devices and picky RS-485 gateways. The connection is
shared by every entry on the same gateway, so when device files disagree, the
largest requested value wins.

**Device-info templates.** `sw_version`, `hw_version` and `serial_number` are
each a Jinja template over the device's register values. Declare the registers
you reference — usually as `internal:` entities, since they need no entity of
their own — and format them with the usual filters, for example
`sw_version: "DSP {{ dsp | round(2) }} ARM {{ arm | round(2) }}"`. They are
rendered once, from the first read.

## Read planning and polling

### Block reads

Each poll cycle collects every entity that is due and merges their registers
into as few block reads as possible:

- overlapping and adjacent spans combine,
- small unused holes up to `max_read_gap` are bridged (reading a few unneeded
  registers is cheaper than a second round trip),
- no block exceeds `max_register_read` or the protocol limit (125 registers,
  2000 bits).

### When a read fails

- **A failed bridged block falls back to unbridged reads** automatically.
- **Filler addresses the device keeps refusing are learned as holes** and never
  bridged again. That takes two bridged reads in a row, and never happens in a
  block whose entities are known alive, since a single miss is as likely a
  transient timeout.
- **A failed retry covering several entities is read once more entity by
  entity**, so one dead register cannot take its readable neighbours down.
- **A register that keeps failing while the device answers everything else is
  quarantined** — after three consecutive polls, or one explicit
  illegal-address answer. Its entity goes unavailable, its registers leave the
  read plan, and a standalone probe every 10 minutes lifts the quarantine as
  soon as the device serves it again. A wrong `address:` costs a warning, a
  repair issue (which clears itself on recovery) and a probe, not permanent
  traffic.
- **Only a register that has never answered can be quarantined.** Once the
  device has served it on two consecutive polls it is known alive for the life
  of the entry and stays in the plan through any later failure. A power-cycled
  device (timing out, then refusing reads while it boots) is therefore polled
  again as soon as it answers.

### Steering the planner

Two device keys steer the planner up front when a device is known to be picky:

- `bad_addresses:` — addresses the device answers with an error, per table;
  the planner never bridges a read across them. This steers only the gaps
  between entities: an entity's own registers are always read, so a register
  the device refuses belongs out of the file, not in this list.
- `split_before:` — a fresh read block must start at these addresses, per
  table; for devices that fail any read *spanning* them.

### Poll intervals

The effective poll interval per entity is `max(floor, cadence)`:

- the **cadence** is the entity's `scan_interval`, else the device file's
  `scan_interval`, else 30 s;
- the **floor** is the larger of the config-entry option (*Minimum update
  interval*) and the device file's `min_scan_interval`. Unset, it imposes no
  floor — it defaults to the config's fastest cadence.

So `scan_interval` sets the actual rate, while `min_scan_interval` and the
option only ever slow polling down.

All polls run on **one shared tick** — the fastest effective interval — so
every register due at that moment shares the same few block reads. An interval
that is not a multiple of the tick polls at the next multiple (45 s next to a
30 s entity polls every 60 s). The integration logs a warning naming those
entities, and *Download diagnostics* lists them under `rounded_intervals`.
Pick intervals that are multiples of the fastest one.

### Writes

**Writes are confirmed** by reading the register back immediately (an entity's
`confirm_delay` defers that read for devices that apply writes slowly). A
write the device rejects is an error. A write it took whose read-back then
fails is only logged and counted as a failed read, and the written value shows
until the next poll.

**A write is skipped when the register already holds the value.** The register
is read first, and if the payload would not change it, nothing is written
(that read is the confirmation). Many devices keep settings in EEPROM or
flash, which survives only a limited number of write cycles, and an automation
re-sending the same setpoint every minute would otherwise wear it out. Command
registers that must act on *every* write — a reset, a start/stop command, a
watchdog refresh — set `write_always: true`. Buttons, `static_value` and
`read_register` entities have no own read-back to compare with and always
write.

### Watching the plan

*Download diagnostics* shows the parsed definition, the planning state
(including learned holes, quarantined and not-yet-alive registers), and
per-entity failure counts (`failed_reads_by_key`, worst first). The entities
that surface failures on the device page are described under
[read health](how_it_works.md#read-health).

## Modbus keys (per entity)

Every entity is a key under one of the four table sections. Besides the
[`ha:` block](#the-ha-block), it takes these keys:

| Group | Keys |
| --- | --- |
| [Address and type](#address-and-type) | `address`, `type`, `count`, `swap` |
| [Converting the value](#converting-the-value) | `multiplier`, `offset`, `map`, `flags`, `mask`, `sum_scale`, `on_value`, `off_value` |
| [Writing](#writing) | `write_value`, `read_register`, `read_modify_write`, `static_value`, `optimistic_default`, `write_multiple`, `confirm_delay`, `write_always` |
| [Filtering and polling](#filtering-and-polling) | `max_change`, `never_resets`, `rectify_time`, `scan_interval` |
| [Visibility](#visibility) | `duplicate_as_sensor`, `internal`, `groups` |

### Address and type

**`address`** — Start address (0–65535, hex `0x…` works).

**`type`** — Value type; determines the register count.

- `uint16` (default), `int16`, `uint32`, `int32`, `uint64`, `int64`,
  `float16`, `float32`, `float64`.
- Sub-word types read one register: `uint8`/`int8` take the low byte, `bit`
  (alias `int1`) the least significant bit.
- `string` needs `count`.
- `time` is HH:MM on a `time` platform — one register (high byte hour, low
  byte minute; add `swap: byte` for the reverse), or `count: 2` for the
  two-register form (first register hour, second minute).
- Bit tables (`coil:`, `discrete:`) are implicitly `bool`.

**`count`** — Register count. Required for `string` (2 characters per
register), `1` or `2` for `time`. For every other type it follows from `type`
(and `sum_scale`) and may only be stated to match.

**`swap`** — `byte`, `word`, or `word_byte` for little-endian devices.

### Converting the value

**`multiplier`** / **`offset`** — `value = raw · multiplier + offset`
(inverted on write).

**`map`** — `{register value: label}` — enums. A `select` requires one and
uses it as its options (labels must be unique). Not combinable with
`multiplier`/`offset` or `flags`.

**`flags`** — `{bit number (0-indexed): name}` — the sensor shows the set
flags as a comma-separated list. `sensor` only, read-only.

**`mask`** — Extract bits: `value = (raw & mask) >> trailing_zeros(mask)` —
integer types only. A writable masked entity also needs `read_modify_write`.

**`sum_scale`** — List of per-element weights:
`value = Σ element[i] · scale[i]`, where each element has the entity's `type`
(default `uint16` — one register per weight). Example
`[1, 10000, 100000000]` for a counter spread over 3 registers.

- With `type: uint8` each register holds two elements (low byte first —
  combine with `swap: byte` for devices that pack the high byte first), so the
  same weights cover 1.5 registers (2 are read).
- With `type: bit` each register holds sixteen (LSB first).
- Writable when the weights are positive integers and the type is an unsigned
  integer.

**`on_value`** / **`off_value`** — Values meaning on/off for
`switch`/`binary_sensor` and open/closed for a binary `valve`.

- Without them, any non-zero value reads as on, and writes use 1/0 (true/false
  on coils).
- With `on_value`: that value reads as on. With no `off_value`, anything else
  is off; with one, other values are unknown.
- `off_value` needs `on_value`.
- These platforms take a plain numeric or bit value — no `map`, `flags` or
  `string`.

### Writing

**`write_value`** — What a `button` writes when pressed.

- A fixed number/boolean **or a single Jinja template** (`"{{ … }}"`) goes
  through the entity's codec, honouring `type`/`map`/`multiplier`/`count` (so
  int32, float, mapped labels, and strings all work).
- A **list** of numbers/templates instead writes each item as one raw 16-bit
  register in a single FC16 transaction — for register blocks like an RTC
  sync: `["{{ now().second }}", "{{ now().minute }}", …]`. The list form
  writes registers, so it cannot target a coil.
- Templates render over the current values with the usual HA functions
  (`now()`, `utcnow()`, …).

**`read_register`** — Take the current value from elsewhere instead of this
entity's own register — a Jinja template like the `template:` section (e.g.
`"{{ other_key }}"`). For settings a device echoes on a different register (or
table) than it accepts writes on: this entity writes to its own
`address`/table, while the referenced entity — often `internal:`, with its own
`type`/`mask`/`multiplier`, and free to live in `input:`/`discrete:` —
supplies the read-back. A plain single-key reference passes the source value
through unchanged (a `time`-typed read-back stays a time-of-day); anything
more is rendered as a template and yields text/numbers.

**`read_modify_write`** — Allow writing a `mask`ed field by merging into the
current register.

**`static_value`** — Marks a write-only command register: never read it — the
entity shows this value until written, then optimistically its last written
value (an option label for a `select`, a number for a `number`). For "direct
control" registers that echo nothing useful, or share an address with an
unrelated read.

**`optimistic_default`** — Read the register as usual, but fall back to this
value when it decodes to nothing (undecodable / out of range) — keeps a
writable control usable instead of unavailable. Mutually exclusive with
`static_value`; neither combines with `read_register`.

**`write_multiple`** — Force FC16 (write-multiple) for the write, even for a
single register — some devices reject FC6 on certain registers (e.g. SolaX
`WRITE_MULTISINGLE`).

**`confirm_delay`** — Seconds to wait between a write and its confirming
read-back (above 0, up to 10) — for devices that apply writes slowly, where an
immediate read still returns the old value.

**`write_always`** — Write even when the register already holds the value. By
default such a write is skipped to spare EEPROM/flash-backed settings (see
[Writes](#writes)); set this on command registers that must act every time
(resets, start/stop commands, watchdog refreshes). Not valid on buttons,
`static_value` or `read_register` entities, which always write.

### Filtering and polling

**`max_change`** — Reject changes larger than this between two polls (spike
filter).

**`never_resets`** — Ignore decreasing values (for `total_increasing`
counters).

**`rectify_time`** — `time`-typed entities only (including `internal:` time
read-backs): show an out-of-range time (e.g. `24:00`, an end-of-day stop time
HA's `time` type cannot represent) as `23:59` instead of dropping the value —
so the slot stays usable.

**`scan_interval`** — Per-entity poll interval in seconds, overriding the
device default. Still raised to `min_scan_interval` if that is longer.

### Visibility

**`duplicate_as_sensor`** — Also create a read-only sensor twin of this
writable entity (any writing platform except `button`), so its history lands
in the recorder/long-term statistics.

**`internal`** — Poll and decode this register for the `template:` section
only — **no Home Assistant entity is created**. So it has no `ha:` block, and
only the decoding keys apply: no `on_value`, `write_value`, `static_value`,
`optimistic_default`, `write_multiple`, `confirm_delay` or
`duplicate_as_sensor`. Internal entities can still be write targets of
template actions (and may set `write_always` for that). If you want the entity
to exist but stay out of sight, use `ha.enabled_by_default: false` instead.

**`groups`** — Tag the entity (or `template:` entry) into named groups, e.g.
`[basic]` or `[advanced]`. The entity is created — and its register polled —
only while at least one of its groups is enabled (`basic` is always enabled).
In a file that uses groups, an entity with no `groups` is shown only while the
*Enable all entities* switch bypasses group handling. See
[Entity groups](#entity-groups).

## The `ha:` block

`platform` selects the entity type; every other key is a field of that
platform's `EntityDescription`.

**Friendly aliases**

| You write | Field it sets |
| --- | --- |
| `unit_of_measurement` or `unit` | `native_unit_of_measurement` |
| `min`, `max`, `step` | `native_min_value`, `native_max_value`, `native_step` |
| `precision` | `suggested_display_precision` |
| `enabled_by_default` | `entity_registry_enabled_default` |

Enum fields (`device_class`, `state_class`, `entity_category`, number/text
`mode`) are validated, with the full list of valid values in the error message.

**Requirements per platform**

- A `number` (register or template) must give `min` and `max` — without a
  range it is rejected. `step` is **not** derived from `multiplier`, so a ×0.1
  setpoint needs `step: 0.1` or it only accepts whole raw values.
- A `text` needs `type: string`.
- A `time` needs `type: time` (and only the `time` platform may use that type).
- A `select` needs a `map`.
- A `button` needs a `write_value`.

**Valves** come in two shapes, chosen by `reports_position`:

- the default is binary — open/close like a switch on a coil or register, with
  `on_value` / `off_value` picking the raw values;
- with `reports_position: true` the register holds a 0–100 position (through
  the usual conversions, register tables only), the valve is closed at 0, and
  set-position writes the percentage back.

**Names.** `name` is the display name; without one it is derived from the
entity key (`pv_power` → "Pv power"). Display names must be **unique within
the device** — two entities showing the same name are indistinguishable in the
UI, so the file is rejected with both keys named (internal entities excepted).
This is checked on the localized names, so a translation must not collapse two
distinct names into one either.

## Entity groups

Big devices expose far more settings and sensors than most people want. Tag
entities (and `template:` entries) with `groups:` to let the user switch whole
sets on and off from the device page. (What the user sees is described in the
[entity groups](entity_groups.md) guide.)

```yaml
device:
  default_groups: [basic, standard]  # what a fresh install (and existing ones) start with
holding:
  battery_soc:
    address: 0
    groups: [basic]              # everyday view (always enabled, no switch)
    ha: {platform: sensor}
  charge_current:
    address: 5
    groups: [standard]           # on by default; the Standard switch can hide it
    ha: {platform: sensor}
  inverter_frequency:
    address: 10
    groups: [advanced]           # off by default; shown when the Advanced switch is on
    ha: {platform: sensor}
  cell_voltage_16:
    address: 20                  # untagged: expert, shown only by "Enable all entities"
    ha: {platform: sensor}
```

### The rules

- An entity is shown when **any** of its groups is enabled.
- `default_groups` picks which groups start enabled. A grouped file without it
  starts with every group enabled.
- **`basic` is special**: it is always enabled and gets no switch. Tagging an
  entity `groups: [basic]` means "part of the always-visible baseline" — it
  keeps the entity out of the other groups without ever letting it be hidden,
  so a user cannot lock themselves out by disabling the group everything lives
  in.
- A file without `groups:` has no switches; it simply shows every entity,
  always.

### The tier convention

The bundled devices follow a **tier convention** on top of this mechanism,
from least to most detail: `basic` (always on), `standard` (on by default —
listed in `default_groups`), then `advanced` (opt-in). Groups are just names,
so this is convention rather than schema. Most entities *also* carry a
**functional group** (e.g. `battery`, `grid`), letting a user switch a whole
subsystem on across every tier.

### Switch names

Each group gets an *Enable ⟨group⟩ entities* switch, the name shown with
underscores as spaces and the first letter capitalized (`parallel_mode` →
*Enable Parallel mode entities*). To override that derived name — for an
acronym, or a name the rule cannot produce — map the group to a label under
`device.group_labels`:

```yaml
device:
  group_labels:
    pm_i1: Parallel mode Inverter 1   # -> "Enable Parallel mode Inverter 1 entities"
    eps: EPS
```

Every key must be a group some entity actually uses.

### The "Enable all entities" switch

Besides the per-group switches there can be one **Enable all entities**
switch. While it is on, group handling is bypassed entirely and every entity
of the file exists — an entity tagged into *no* group is exactly the
"everything else" tier behind that switch.

It is offered only where it adds something: when the file has untagged
entities, or at least four toggleable groups (so enabling everything one
switch at a time would be a chore). A file with a couple of groups and no
untagged entity gets group switches only, which already reach every entity.

`all` is not a reserved name: a file may declare a group called `all`, which
behaves like any other named group.

### Hidden entities and the read plan

Hidden entities also drop out of the Modbus read plan. A shown template,
`read_register`, `write_value`, or action selector keeps its own source
registers polled even when those sources are hidden (as do the device-info
templates `sw_version`/`hw_version`/`serial_number`), so a visible value never
loses its inputs.

## The `template:` section

Composite entities built from the device's values with real Home Assistant
Jinja templates.

- Every entity key of the device file is available as a plain variable (and
  via the `values` dict). All normal HA template functions work too.
- **`key('some_entity')`** is one extra helper: it returns the raw register
  value behind a mapped entity's current option (its `map:` key) instead of
  the decoded label. `key('operating_mode') == 0` is a stable,
  language-independent test where `operating_mode == 'Off'` is not (see
  [Translations](#translations)). For an entity without a `map:`, `key()` just
  returns its value.
- Templates re-render on every device poll.

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

### Write actions

Write actions (`turn_on`, `set_temperature`, …) target one of the device's
entities by key — through the same codec as everything else, so multipliers,
offsets, and select maps apply.

**Valid targets** live in a writable table (`holding:`/`coil:`) and may be
`internal`. A `button`, a `time` entity, a `flags` entity, or a masked entity
without `read_modify_write` cannot be a target, since no action payload could
be encoded for it.

**Three kinds of action**

| Kind | Form | What is written |
| --- | --- | --- |
| fixed | `{entity: x, value: 1}` | the given value — on/off/open/close/stop. Against a `map:`ped target the value is one of its labels, e.g. `value: "On"` |
| value-carrying | `{entity: x}` | the UI value |
| mapped | `{entity: x, map: {ui value: written value}}` | the UI value, translated through the map |

Payloads are checked against the target at load time: a mapped target takes
exactly its labels, a plain register takes numbers.

### Choosing the target at write time (`by` / `cases`)

Instead of a single `entity`, any action may choose its target at write time
with `by`/`cases`: the `by` template is rendered and its value selects a case,
each case being an ordinary target (with its own optional `value`/`map`).
Every case is validated and codec-routed like a normal target; a rendered
value with no matching case raises an error instead of writing to the wrong
register. This lets one control write to different registers depending on
another value — e.g. a thermostat whose active setpoint follows a
regulation-type selector:

```yaml
set_temperature:
  by: "{{ regulation_mode }}"          # rendered on each write; its value picks a case
  cases:
    supply:  {entity: supply_setpoint}
    room:    {entity: room_setpoint}
    exhaust: {entity: exhaust_setpoint}
```

The read side needs no special construct — a template already sees every
value, so `current_temperature`/`target_temperature` can switch inputs with a
plain `{{ {'supply': t_supply, 'room': t_room}[regulation_mode] }}`.

### Template platforms

| Template platform | Templates | Actions | Statics |
| --- | --- | --- | --- |
| `sensor`, `binary_sensor` | `state` | — | `integrate` (sensor only, see below) |
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

### Integrating a rate into a total (`integrate`)

For values the device offers no native counter for, a template sensor may
declare `integrate: trapezoidal` (or `left`/`right`): the `state` template then
yields instantaneous power in **watts**, and the sensor accumulates
**kilowatt-hours** with that Riemann-sum method across polls — ready for HA's
Energy Dashboard without setting up an Integral helper. The total survives
restarts; any interval where the source is unavailable (or HA was down) is
skipped, never interpolated. Clamp the source if only one direction should
count:

```yaml
template:
  pv_energy_1:
    state: "{{ [pv_power_1 or 0, 0] | max }}"   # W, production only
    integrate: trapezoidal
    ha:
      platform: sensor
      device_class: energy
      state_class: total_increasing
      unit_of_measurement: kWh
```

That string form is the energy shorthand, so its unit must be kWh (or left out).
For any other rate use the mapping form, which names the time unit the rate is
per — `s`, `min`, `h`, or `d` — and accumulates `Σ value × Δt / per` in whatever
unit the sensor declares. A flow in litres per hour totals litres:

```yaml
template:
  water_used:
    state: "{{ flow_rate }}"                    # L/h
    integrate: {method: trapezoidal, per: h}
    ha:
      platform: sensor
      device_class: water
      state_class: total_increasing
      unit_of_measurement: L
```

No prefix is applied in this form; scale in the template if you need one
(`{{ power / 1000 }}` with `per: h` turns watts into kWh, like the shorthand).

### Why not Home Assistant's template integration?

Its platform setup is internal API (and core has no template *climate*), its
entities would not belong to this device or unload with it, and you would have
to reference global entity IDs instead of the device's keys. The Jinja engine
used here *is* Home Assistant's own — only the thin entity glue is local.

## Translations

Human-facing strings default to a single language — whatever you write is shown
verbatim. To offer more than one language, add a top-level `translations:`
block that maps a **source string** (the text as it appears elsewhere in the
file) to its per-language variants:

```yaml
translations:
  Brine/water heat pump SI 11TU:      # the source string, used as the lookup key
    en: Brine/water heat pump SI 11TU
    de: Sole/Wasser-Wärmepumpe SI 11TU
  Schedule / time program:
    en: Schedule / time program
    de: Zeitplan / Zeitprogramm
  Summer:
    en: Summer
    de: Sommer

device:
  model: Brine/water heat pump SI 11TU      # ← translated via the catalog
  group_labels:
    schedule: Schedule / time program       # ← translated
holding:
  operating_mode:
    address: 1
    map:
      0: Summer                              # ← map/flag values translated
      1: Winter
    ha:
      platform: select
      name: Operating mode                   # ← entity names translated
```

On load, the integration picks the language from Home Assistant's configured
language (**Settings → System → General**) and rewrites each translatable
string in place. It never changes what your `.yaml` says — the source strings
stay the lookup keys, so you keep authoring in one language (typically
English) and the catalog supplies the rest.

**What is translated:** the device `model`, `group_labels`, every
entity/template `ha: name`, and `map:` / `flags:` values.

**What is not:** `manufacturer` (a brand), `prefix`, and entity keys — those
must stay stable because they seed entity IDs.

**Lookup order** for a string found in the catalog: the exact configured
language (e.g. `de`), then its base language (`de-DE` → `de`), then `en`, and
finally the source string itself. A string that is not a catalog key — and
*every* string when there is no `translations:` block — is used verbatim. So
partial catalogs are fine: translate what you have, and the rest falls back to
English.

Three things to keep in mind:

- **It is the server's language, not per-user.** Home Assistant resolves these
  names once, in the backend, using the instance language; every user sees the
  same strings. (This is the same limitation HA itself has for dynamically
  named entities.) Changing the language takes effect after the integration
  reloads.
- **A translated `map:` value becomes the entity's stored state** (e.g. the
  state is `Sommer` rather than `Summer`). That is what the recorder stores and
  what automations comparing option text must match, so switching languages
  changes those stored strings. Keep each language's values unique, just as
  option text must already be unique in one language.
- **Inside `template:` entries, compare the map _key_, not the label.** A test
  like `operating_mode == 'Sommer'` breaks once `Sommer` is translated (the
  decoded value follows the language, the literal in the template does not).
  Use the `key()` helper — `key('operating_mode') == 0` — which returns the
  stable register value and never moves. The same applies to a mapped write
  action: its values *are* translated in lockstep with the target's `map:` (so
  `set_hvac_mode: {map: {heat: Sommer}}` keeps working), but a plain-string
  comparison in a template does not. When you add translations to a file that
  has templates referencing enum values, migrate those comparisons to `key()`.

## Validating and debugging a file

**In the editor.** For autocomplete and inline validation while editing, put
this as the first line of the file (VS Code needs the YAML extension; most
editors with a YAML language server work):

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/dmatscheko/modbus_connect/main/docs/device_files.schema.json
```

The [schema](device_files.schema.json) knows every Modbus key, the per-platform
`ha:` fields (generated from the same Home Assistant introspection the
integration validates with), and the `template:` shapes — typos and
wrong-platform fields are flagged as you type. It is an editor-side typo net;
the integration's own validation on load stays authoritative for cross-field
rules.

**On load.** Schema errors are loud by design: the setup dialog's device
picker and the log name the file, the entity, and the reason — enum fields
even list every valid value. A file whose `device:` block cannot be read is
left out of the picker with a note; an error further down is reported when the
file is selected.

**Once it runs.** *Download diagnostics* on the device page shows the parsed
definition, the read-planning state, and the current values.
[Troubleshooting](troubleshooting.md) covers wrong values (byte order,
multipliers) and unreachable registers.

**Against the device.** Before a file exists, or when a register misbehaves,
look at the device itself. The
[Modbus Scanner](../support/modbus_scanner/README.md) walks its registers in a
browser, shows what answers and changes, decodes every reading, maps registers
to entities by clicking, and generates a file from the result.
`support/modbus_cli.py` does one-off probes, reads with every common decoding
next to the raw words (so `type`/`swap` can be read straight off), writes, and
range scans that print ready-to-paste `bad_addresses:`/`split_before:` keys
from a terminal (`--help`). Both are introduced in
[writing a device file](writing_a_device_file.md#2-look-at-the-live-device).

Pull requests with new device files are welcome — see
[contributing](../CONTRIBUTING.md#adding-a-device-file).
