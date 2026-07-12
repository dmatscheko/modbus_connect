# Controller-style extensions

Almost everything a device does maps cleanly onto Modbus Connect's declarative
device files: a register you read, a register you write, or a value you compute
from other registers with a Jinja `template`. A small number of features don't —
they are not *values* but *control loops*: they run continuously, keep state
between polls, react to live measurements, and write several registers per tick.

This note documents the clearest real example (SolaX's mode 8/9 power-control
button), explains why it can't be a device-file entity today, what you *can*
already do, and sketches how the integration might support such extensions in
the future. It exists because this class of feature is genuinely useful —
dynamic-tariff / negative-price battery optimisation, small VPP-style control —
and worth revisiting.

## The worked example: SolaX "PowerControlMode Trigger (mode 8/9)"

Upstream [homeassistant-solax-modbus](https://github.com/wills106/homeassistant-solax-modbus)
defines a button:

```
key            powercontrolmode8_trigger
name           PowerControlMode Trigger (mode 8/9)
register       0xA0
write_method   WRITE_MULTI_MODBUS
value_function autorepeat_function_powercontrolmode8_recompute
autorepeat     remotecontrol_autorepeat_duration
allowedtypes   AC | HYBRID | GEN4 | GEN5 | GEN6
```
(`plugin_solax.py:1501`; the loop is `plugin_solax.py:709`.)

### What it actually does

SolaX hybrids can be driven externally through a **remote-control** register
block instead of running their built-in self-use logic. You give the inverter
setpoints — push-mode (battery) power, PV power limit, target/minimum SoC, an
active-power target — and it obeys them. Modes 1–7 are the older push/self-use
set; **modes 8 and 9 are SolaX's newer "Power Control Mode"** for finer
active-power and battery steering (SolaX KB:
`https://kb.solaxpower.com/solution/detail/2c9fa4148ecd09eb018edf67a87b01d2`).

The catch: this interface is a **watchdog**. If the controller stops writing
within `remotecontrol_timeout`, the inverter reverts to normal operation. You
cannot set it once — you must keep re-sending setpoints to hold the mode.

So the button is an *autorepeat* button. One press starts a loop that runs for
`remotecontrol_autorepeat_duration` seconds, calling the recompute function each
tick in three phases:

1. **First tick** — read ~20 live inputs (PV power, house load, battery SoC,
   measured grid power, SoC bounds, and the strategy knobs below), run the
   selected strategy, and write the resulting setpoints as one
   `WRITE_MULTI_MODBUS` transaction.
2. **Loop ticks** (every few seconds) — recompute from fresh measurements *and*
   the setpoints it stored last tick (`remotecontrol_current_pv_power_limit`,
   `remotecontrol_current_pushmode_power`), applying setpoint filters and
   deadbands to avoid oscillation, respecting BMS charge caps and SoC limits,
   then re-write. This is a genuine closed-loop controller: measured grid power
   is the error signal, and the PV limit / battery power move in bounded steps.
3. **Final tick** — clear the stored state and write
   `remotecontrol_power_control_mode = Disabled`, handing control back to the
   inverter.

The strategy is chosen by the `remotecontrol_power_control_mode` select, e.g.:

- **Negative Injection Price** — when export prices go negative, avoid exporting:
  bias slightly toward grid import, soak surplus PV into the battery up to the
  target SoC, and modulate the PV limit using measured export as feedback.
- **Negative Injection and Consumption Price** — when both are negative: stop PV
  (`pvlimit = 0`) and charge the battery as fast as the import limit / BMS allow.
- **PV and BAT control – Duration**, **Feed-in Priority**, **No Discharge** —
  other direct-control variants.

### The moving parts

Strategy knobs the loop reads (ordinary settings you can set in advance):

```
remotecontrol_power_control_mode   remotecontrol_set_type
remotecontrol_pv_power_limit       remotecontrol_import_limit
remotecontrol_push_mode_power_8_9  remotecontrol_timeout
remotecontrol_target_soc_8_9       remotecontrol_autorepeat_duration
remotecontrol_minimum_soc_8_9      remotecontrol_timeout_next_motion
```

Loop-internal state (computed, no register — exposed upstream as sensors):

```
remotecontrol_current_pv_power_limit
remotecontrol_current_pushmode_power
remotecontrol_autorepeat_remaining
```

## Why it doesn't fit a device file

Modbus Connect device files are declarative, and a device-file "write" is one of
exactly two shapes:

- a **fixed write** — a button/number/select puts a known value into a register; or
- a **template render** — `write_value` / a `template` entity renders Jinja
  **once, statelessly**, over the current `coordinator.data` (the latest entity
  values) and produces a value.

The mode 8/9 button is neither. It needs things the declarative model has no seat
for: **persistent state across polls**, a **periodic timer**, **feedback** from
live measurements, a **multi-register transactional write** each tick, and a
**teardown** step. A one-shot stateless render cannot express a control loop.

That is why it was dropped when SolaX was imported: any button carrying a
`value_function` was skipped, the same way register-less computed sensors were —
so it is simply absent from the owned `support/devicedocs/solax-x3-hybrid-g4/device.yaml`.

## What you *can* do today

The individual setpoints are **not** the problem — only the orchestration is.
Upstream also exposes the raw registers as a `*_direct` cluster:

```
remotecontrol_active_power_direct        remotecontrol_pv_power_limit_direct
remotecontrol_charge_discharge_power_direct  remotecontrol_push_mode_power_8_9_direct
remotecontrol_push_mode_power_direct     remotecontrol_duration_8_direct
remotecontrol_target_soc_direct          remotecontrol_target_soc_9_direct
remotecontrol_target_energy_direct       remotecontrol_timeout_8_9_direct
remotecontrol_duration_direct            remotecontrol_timeout_direct
```

These are plain register writes, so they model fine as ordinary `number` /
`select` entities on real registers in a device file. With those exposed, the
control loop itself can live in a **Home Assistant automation** (or blueprint):
read the sensors, decide, write the `*_direct` setpoints, and repeat on a timer
fast enough to beat `remotecontrol_timeout`. That keeps device files declarative
and puts the stateful part where HA already has state, triggers, and templating.

## Sketch: first-class support later

Rough options, least to most integration work:

1. **Reference blueprint (no code change).** Expose the `*_direct` registers in
   the device file and ship a documented automation/blueprint that runs the loop
   and keeps the watchdog fed. Cheapest; leaves the algorithm in the user's hands.
2. **A device-file `controller` hook.** Let a device file opt in to a named
   Python controller invoked each refresh with read access to entity values,
   a small persistent state dict, and a write API. Device files stay declarative
   for the 99%; controllers are the explicit escape hatch for the 1%. Needs a
   loading/trust story (bundled-only vs. user-supplied) and tests.
3. **A declarative "sequence" primitive.** A device-file construct that declares
   inputs, a recompute expression, output registers, a tick interval, and a
   watchdog keep-alive — executed statefully by the integration. Most expressive,
   most design and safety work (writing power setpoints in a loop is not a place
   for surprises).

Whatever the shape, the load-bearing requirements are the same: persistent
per-entity state, a timer, transactional multi-register writes, a clean teardown,
and enough sandboxing/testing that a misbehaving controller can't wedge the
device.

## References

- Upstream button + loop: `homeassistant-solax-modbus`
  `custom_components/solax_modbus/plugin_solax.py:1501` and `:709`.
- Time/`value_function` handling and skips: the original SolaX importer (removed once the
  device became owned in-tree; see its history under `support/converter/` in git).
- Device-file format (what *is* expressible): [docs/device_files.md](../docs/device_files.md).
