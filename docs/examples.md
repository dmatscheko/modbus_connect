# Examples

Entities from Modbus Connect behave like any other Home Assistant entities, so
dashboards, automations and the Energy Dashboard use them directly.

- [Energy Dashboard with a SolaX X3-Hybrid G4](#energy-dashboard-with-a-solax-x3-hybrid-g4)
- [Automations](#automations)

## Energy Dashboard with a SolaX X3-Hybrid G4

Everything the [Energy Dashboard](https://www.home-assistant.io/docs/energy/)
needs is an entity of the bundled hybrid inverter file. Some of them sit in
[entity groups](entity_groups.md) that are off by default — enable the group
named in the last column first.

| Dashboard slot | Entity key | Group |
| --- | --- | --- |
| Grid consumption | `import_energy_today` | `standard` (on by default) |
| Return to grid | `export_energy_today` | `standard` (on by default) |
| Solar production | `solar_energy_today` | `basic` (always on) |
| — per string | `pv_energy_1`, `pv_energy_2` | `solar_details` |
| Battery in | `battery_input_energy_today` | `standard` (on by default) |
| Battery out | `battery_output_energy_today` | `standard` (on by default) |
| Grid → battery | `e_charge_today`, live `grid_to_battery_power` | `grid_to_battery` |
| Home consumption | `home_consumption_energy`, live `house_load` | `home_consumption` |

Coming from the solax-modbus integration? The `solar_details`,
`home_consumption` and `grid_to_battery` groups correspond to its *Enable PV
Variant Detail / Home Consumption / Grid to Battery Sensors* switches. There
the values are copies on a virtual device; here the groups reveal the real
sensors.

Some of these kWh sensors have no native counter on the inverter. They
integrate the matching power over time — a device-file feature
([`integrate`](device_files.md#integrating-a-rate-into-a-total-integrate)), so
no Integral helper is needed.

## Automations

Boost the ventilation while cooking (a Pichler unit's fan entity):

```yaml
automation:
  - alias: Boost ventilation while cooking
    triggers:
      - trigger: state
        entity_id: binary_sensor.kitchen_hood_running
        to: "on"
    actions:
      - action: fan.set_preset_mode
        target:
          entity_id: fan.pichler_lg_ventilation
        data:
          preset_mode: Stufe 3
```

Send a notification when an inverter reports a fault (a Growatt fault-code
sensor):

```yaml
automation:
  - alias: Warn on inverter fault
    triggers:
      - trigger: state
        entity_id: sensor.growatt_mod_6000tl_x_fault_code
    conditions: "{{ trigger.to_state.state not in ('0', 'unknown', 'unavailable') }}"
    actions:
      - action: notify.mobile_app_phone
        data:
          message: "Inverter fault: {{ trigger.to_state.state }}"
```

Your entity IDs depend on the name and prefix you chose during
[setup](../README.md#setup) — look them up on the device page.

A tip for automations that set a value repeatedly: a write is skipped when the
register already holds that value, so re-sending the same setpoint every minute
does not wear out the device's memory. See
[how it works](how_it_works.md#writes).
