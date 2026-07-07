# Modbus Connect

A Home Assistant custom integration for Modbus devices behind local TCP
gateways — a ground-up rewrite of
[modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway) built
around three ideas:

1. **Block reads.** Instead of one Modbus round trip per entity, each poll
   merges everything into as few reads as possible: overlapping and adjacent
   registers combine, small unused holes are bridged (cheaper to read than to
   ask twice), and blocks respect the device's `max_register_read` and the
   protocol limit of 125 registers. Real device files: an Eastron SDM630 drops
   from 85 transactions per poll to 7; a Pichler LG350 from 129 to 5.
2. **Home Assistant is not shadowed.** Every entity has an `ha:` block that is
   passed to the real per-platform `EntityDescription` and validated against
   it — any entity feature HA supports (today or in a future release) can be
   set there, and typos fail loudly with the file, entity, and valid choices
   in the message.
3. **Symmetric conversions.** Whatever the integration can decode it can also
   encode for writing (`multiplier`/`offset`, `map`, `sum_scale`, masked bit
   fields via read-modify-write). Only `flags` is inherently read-only.

Failed bridged blocks fall back to unbridged reads automatically, and
addresses a device refuses to serve are remembered and never bridged again.
Offline devices back off exponentially (up to 5 min) instead of hammering the
gateway. One failing entity does not take down the rest; it just becomes
unavailable.

## Installation

Copy `custom_components/modbus_connect/` into `<ha_config>/custom_components/`
(or add this repository as a custom HACS repository). Restart Home Assistant,
then add the **Modbus Connect** integration: enter the gateway host/port and
slave ID, then pick a device file.

It can be installed side by side with `modbus_local_gateway`; entities are
independent.

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

```yaml
device:
  manufacturer: Eastron
  model: SDM630
  max_register_read: 100   # max registers per read request (default 8, cap 125)
  max_read_gap: 8          # bridge unused holes up to this many registers (default 8)
  scan_interval: 30        # default poll interval in seconds (optional)

input:
  phase_1_voltage:
    address: 0x0000        # register/coil address (decimal or hex)
    type: float32          # uint16 (default) | int16 | uint32 | int32 | uint64 |
                           # int64 | float32 | float64 | string
    ha:
      platform: sensor     # sensor | binary_sensor | number | select | switch |
                           # text | button
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

### Modbus keys (per entity)

| Key | Meaning |
| --- | --- |
| `address` | Start address (0–65535, hex `0x…` works) |
| `type` | Value type; determines register count. `string` needs `count`. Bit tables are implicitly `bool` |
| `count` | Register count — only for `string` (2 characters per register) |
| `swap` | `byte`, `word`, or `word_byte` for little-endian devices |
| `sum_scale` | List of per-word weights: `value = Σ word[i] · scale[i]`. Example `[1, 10000, 100000000]` for values spread over 3 registers. Writable when the weights are positive integers |
| `mask` | Extract bits: `value = (raw & mask) >> trailing_zeros(mask)`. Replaces the old `bits`/`shift_bits` pair |
| `multiplier` / `offset` | `value = raw · multiplier + offset` (inverted on write) |
| `map` | `{register value: label}` — enums; used as the options of a `select` |
| `flags` | `{bit number (0-indexed): name}` — sensor shows the set flags, read-only |
| `on` / `off` | Values meaning on/off for `switch`/`binary_sensor` (defaults: 1/0, true/false) |
| `write_value` | Value a `button` writes when pressed |
| `read_modify_write` | Allow writing a `mask`ed field by merging into the current register |
| `max_change` | Reject changes larger than this between two polls (spike filter) |
| `never_resets` | Ignore decreasing values (for `total_increasing` counters) |
| `scan_interval` | Per-entity poll interval in seconds (overrides the default) |
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

## Migrating from modbus_local_gateway

Convert old device files with the standalone converter (needs only PyYAML):

```bash
python3 converter/convert.py <old_device_configs_or_files> -o <output_dir>
```

The converter preserves semantics — the four old sections map 1:1 onto
`holding:`/`input:`/`coil:`/`discrete:` — and prints a warning for everything
it has to change or drop. What changes:

- `control:` becomes `ha.platform`.
- `float`/`signed`/`string`/`size` collapse into `type:` (+ `count` for strings).
- `bits`/`shift_bits` become a single `mask`.
- `flags` bit numbers are 0-indexed now (the converter shifts them).
- Unit presets (`Volts`, `Celsius`, …) are expanded to real units plus the
  device/state class they implied.
- HA fields (`name`, `icon`, `device_class`, `entity_category`,
  `precision`, …) move into the `ha:` block.
- Number `precision` is dropped (HA numbers have no display precision;
  use `ha.step`).

Because this is a new integration (new domain), Home Assistant treats the
entities as new; dashboards and automations need to be pointed at them.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install pytest-homeassistant-custom-component pymodbus ruff pyyaml
.venv/bin/python -m pytest tests/
.venv/bin/ruff check custom_components tests converter
```

Layout: `models.py` (plain dataclasses), `codec.py` (registers ↔ values,
pure), `planner.py` (block planning, pure), `client.py` (pymodbus wrapper),
`schema.py` (YAML validation), `coordinator.py` (polling, cache, backoff,
writes), `entity.py` + thin platform modules including template-driven
`climate.py`. The pure modules have no Home Assistant imports and are tested
standalone; `tests/test_e2e_server.py` proves the transaction counts against
a real TCP server.
