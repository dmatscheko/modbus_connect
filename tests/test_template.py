"""Runtime tests for template: entities."""

import pytest
import yaml
from homeassistant.components.climate import HVACMode
from homeassistant.exceptions import ServiceValidationError

from custom_components.modbus_connect.binary_sensor import ModbusConnectTemplateBinarySensor
from custom_components.modbus_connect.climate import ModbusConnectClimate
from custom_components.modbus_connect.const import OPTION_ENABLED_GROUPS, OPTION_SHOW_ALL
from custom_components.modbus_connect.cover import ModbusConnectCover
from custom_components.modbus_connect.entity import build_template_description
from custom_components.modbus_connect.fan import ModbusConnectFan
from custom_components.modbus_connect.light import ModbusConnectLight
from custom_components.modbus_connect.loader import BUILTIN_DIR, _load_file
from custom_components.modbus_connect.number import ModbusConnectTemplateNumber
from custom_components.modbus_connect.schema import parse_device
from custom_components.modbus_connect.select import ModbusConnectTemplateSelect
from custom_components.modbus_connect.sensor import (
    ModbusConnectIntegralSensor,
    ModbusConnectTemplateSensor,
)
from custom_components.modbus_connect.switch import ModbusConnectTemplateSwitch

from .fakes import FakeClient, FakeTime, make_coordinator

DEVICE_YAML = """
device:
  manufacturer: Acme
  model: HeatPump

holding:
  temp:
    address: 0
    type: int16
    multiplier: 0.1
    ha: {platform: sensor}
  setpoint:              # only used by the climate entity — hidden from HA
    address: 1
    multiplier: 0.5
    internal: true
  mode:                  # only used by the climate entity — hidden from HA
    address: 2
    map: {0: "Off", 1: "Auto"}
    internal: true
  power:
    address: 3
    ha: {platform: sensor}
  fan_speed:             # 0-100 %
    address: 4
    internal: true
  fan_power:             # 0/1
    address: 5
    internal: true
  cover_pos:             # 0-100, 0 = closed
    address: 6
    internal: true
  cover_cmd:             # 0 stop, 1 open, 2 close
    address: 7
    internal: true
  light_level:           # 0-255
    address: 8
    internal: true

template:
  ventilation:
    ha: {platform: fan, name: Ventilation}
    state: "{{ fan_power == 1 }}"
    percentage: "{{ fan_speed }}"
    turn_on: {entity: fan_power, value: 1}
    turn_off: {entity: fan_power, value: 0}
    set_percentage: {entity: fan_speed}

  shutter:
    ha: {platform: cover, device_class: shutter}
    position: "{{ cover_pos }}"
    open_cover: {entity: cover_cmd, value: 1}
    close_cover: {entity: cover_cmd, value: 2}
    stop_cover: {entity: cover_cmd, value: 0}
    set_position: {entity: cover_pos}

  panel_light:
    ha: {platform: light}
    state: "{{ light_level > 0 }}"
    brightness: "{{ light_level }}"
    turn_on: {entity: light_level, value: 255}
    turn_off: {entity: light_level, value: 0}
    set_brightness: {entity: light_level}

  boost:
    ha: {platform: switch}
    state: "{{ fan_speed > 80 }}"
    turn_on: {entity: fan_speed, value: 100}
    turn_off: {entity: fan_speed, value: 50}

  speed_number:
    ha: {platform: number, name: Speed, min: 0, max: 100}
    state: "{{ fan_speed }}"
    set_value: {entity: fan_speed}

  mode_select:
    ha: {platform: select}
    state: "{{ mode }}"
    select_option: {entity: mode}
  cop:
    state: "{{ (power / 100) | round(2) }}"
    ha: {platform: sensor, precision: 2}
  is_hot:
    state: "{{ temp > 30 }}"
    ha: {platform: binary_sensor}
  hot_water:
    ha: {platform: climate, name: Hot water}
    current_temperature: "{{ temp }}"
    target_temperature: "{{ setpoint }}"
    hvac_mode: "{{ 'heat' if mode == 'Auto' else 'off' }}"
    min_temp: 20
    max_temp: 60
    temp_step: 0.5
    set_temperature: {entity: setpoint}
    set_hvac_mode: {entity: mode, map: {heat: "Auto", "off": "Off"}}
"""

# registers: temp=352 (35.2), setpoint=90 (45.0), mode=1 (Auto), power=250,
# fan 66% running, cover at 30, light at 128
REGISTERS = {0: 352, 1: 90, 2: 1, 3: 250, 4: 66, 5: 1, 6: 30, 7: 0, 8: 128}


async def setup_device(hass, monkeypatch):
    device = parse_device(yaml.safe_load(DEVICE_YAML), "heatpump.yaml")
    client = FakeClient(dict(REGISTERS))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    return device, client, coordinator


def template_def(device, key):
    return next(t for t in device.templates if t.key == key)


def make_entity(hass, cls, coordinator, tdef):
    entity = cls(coordinator, tdef, build_template_description(tdef))
    entity.hass = hass
    return entity


async def test_internal_entities_polled_but_hidden(hass, monkeypatch):
    device, _, coordinator = await setup_device(hass, monkeypatch)
    internals = {e.key for e in device.entities if e.internal}
    assert internals == {
        "setpoint", "mode", "fan_speed", "fan_power", "cover_pos", "cover_cmd",
        "light_level",
    }
    # polled and decoded like any entity, so templates can use them ...
    assert coordinator.data["setpoint"] == pytest.approx(45.0)
    assert coordinator.data["mode"] == "Auto"
    # ... but no platform will ever create an HA entity for them
    assert all(
        e.platform not in ("sensor", "binary_sensor", "number", "select",
                           "switch", "text", "button")
        for e in device.entities if e.internal
    )


async def test_template_sensor_renders(hass, monkeypatch):
    device, _, coordinator = await setup_device(hass, monkeypatch)
    sensor = make_entity(hass, ModbusConnectTemplateSensor, coordinator,
                         template_def(device, "cop"))
    assert sensor.native_value == pytest.approx(2.5)


async def test_template_binary_sensor(hass, monkeypatch):
    device, client, coordinator = await setup_device(hass, monkeypatch)
    binary = make_entity(hass, ModbusConnectTemplateBinarySensor, coordinator,
                         template_def(device, "is_hot"))
    assert binary.is_on is True  # 35.2 > 30

    client.values[("holding", 0)] = 100  # 10.0 degrees
    coordinator._next_due = dict.fromkeys(coordinator._next_due, 0.0)
    await coordinator.async_refresh()
    assert binary.is_on is False


async def test_climate_state_from_templates(hass, monkeypatch):
    device, _, coordinator = await setup_device(hass, monkeypatch)
    climate = make_entity(hass, ModbusConnectClimate, coordinator,
                          template_def(device, "hot_water"))
    assert climate.current_temperature == pytest.approx(35.2)
    assert climate.target_temperature == pytest.approx(45.0)
    assert climate.hvac_mode == HVACMode.HEAT
    assert set(climate.hvac_modes) == {HVACMode.HEAT, HVACMode.OFF}
    assert climate.min_temp == 20
    assert climate.max_temp == 60
    assert climate.target_temperature_step == pytest.approx(0.5)


async def test_climate_set_temperature_writes_through_codec(hass, monkeypatch):
    device, client, coordinator = await setup_device(hass, monkeypatch)
    climate = make_entity(hass, ModbusConnectClimate, coordinator,
                          template_def(device, "hot_water"))
    await climate.async_set_temperature(temperature=50.0)
    # setpoint has multiplier 0.5 -> raw register 100
    assert client.written == [(1, [100])]
    # read-back confirmed the new value; template sees it immediately
    assert climate.target_temperature == pytest.approx(50.0)


async def test_climate_set_hvac_mode_maps_to_select_option(hass, monkeypatch):
    device, client, coordinator = await setup_device(hass, monkeypatch)
    climate = make_entity(hass, ModbusConnectClimate, coordinator,
                          template_def(device, "hot_water"))
    await climate.async_set_hvac_mode(HVACMode.OFF)
    # "off" -> option "Off" -> register value 0 via the select's map
    assert client.written == [(2, [0])]

    await climate.async_turn_on()
    assert client.written[-1] == (2, [1])  # "heat" -> "Auto" -> 1


async def test_template_fan(hass, monkeypatch):
    device, client, coordinator = await setup_device(hass, monkeypatch)
    fan = make_entity(hass, ModbusConnectFan, coordinator,
                      template_def(device, "ventilation"))
    assert fan.is_on is True
    assert fan.percentage == 66

    await fan.async_set_percentage(80)
    assert client.written[-1] == (4, [80])
    assert fan.percentage == 80  # read-back confirmed

    await fan.async_set_percentage(0)  # 0 % means turn off
    assert client.written[-1] == (5, [0])
    assert fan.is_on is False

    await fan.async_turn_on()
    assert client.written[-1] == (5, [1])


async def test_template_cover(hass, monkeypatch):
    device, client, coordinator = await setup_device(hass, monkeypatch)
    cover = make_entity(hass, ModbusConnectCover, coordinator,
                        template_def(device, "shutter"))
    assert cover.current_cover_position == 30
    assert cover.is_closed is False

    await cover.async_close_cover()
    assert client.written[-1] == (7, [2])
    await cover.async_stop_cover()
    assert client.written[-1] == (7, [0])
    await cover.async_set_cover_position(position=75)
    assert client.written[-1] == (6, [75])
    assert cover.current_cover_position == 75

    await cover.async_set_cover_position(position=0)
    assert cover.is_closed is True  # position 0 = closed


async def test_template_light(hass, monkeypatch):
    device, client, coordinator = await setup_device(hass, monkeypatch)
    light = make_entity(hass, ModbusConnectLight, coordinator,
                        template_def(device, "panel_light"))
    assert light.is_on is True
    assert light.brightness == 128

    await light.async_turn_off()
    assert client.written[-1] == (8, [0])
    assert light.is_on is False

    await light.async_turn_on(brightness=200)
    assert client.written[-1] == (8, [200])
    assert light.brightness == 200

    await light.async_turn_on()  # without brightness: fixed turn_on value
    assert client.written[-1] == (8, [255])


async def test_template_switch(hass, monkeypatch):
    device, client, coordinator = await setup_device(hass, monkeypatch)
    switch = make_entity(hass, ModbusConnectTemplateSwitch, coordinator,
                         template_def(device, "boost"))
    assert switch.is_on is False  # 66 is not > 80
    await switch.async_turn_on()
    assert client.written[-1] == (4, [100])
    assert switch.is_on is True
    await switch.async_turn_off()
    assert client.written[-1] == (4, [50])


async def test_template_number(hass, monkeypatch):
    device, client, coordinator = await setup_device(hass, monkeypatch)
    number = make_entity(hass, ModbusConnectTemplateNumber, coordinator,
                         template_def(device, "speed_number"))
    assert number.native_value == 66
    await number.async_set_native_value(42)
    assert client.written[-1] == (4, [42])


async def test_template_select_options_from_target_map(hass, monkeypatch):
    device, client, coordinator = await setup_device(hass, monkeypatch)
    select = make_entity(hass, ModbusConnectTemplateSelect, coordinator,
                         template_def(device, "mode_select"))
    assert select.options == ["Off", "Auto"]  # derived from the target's map
    assert select.current_option == "Auto"
    await select.async_select_option("Off")
    assert client.written[-1] == (2, [0])  # written through the target's map


# A ventilation unit whose active temperature setpoint is chosen by a
# regulation-type selector: the climate must read AND write the right pair.
SWITCH_YAML = """
device: {manufacturer: Acme, model: HRV}
holding:
  regelungsart:
    address: 0
    map: {1: Abluft, 2: Zuluft, 3: Raum}
    ha: {platform: select, name: Regelungsart}
  soll_zuluft:
    address: 1
    multiplier: 0.1
    ha: {platform: number, min: 10, max: 40, name: Soll Zuluft}
  soll_raum:
    address: 2
    multiplier: 0.1
    ha: {platform: number, min: 10, max: 40, name: Soll Raum}
  t_zuluft: {address: 3, multiplier: 0.1, internal: true}
  t_raum: {address: 4, multiplier: 0.1, internal: true}

template:
  klima:
    ha: {platform: climate, name: Klima}
    current_temperature: "{{ {'Zuluft': t_zuluft, 'Raum': t_raum}.get(regelungsart) }}"
    target_temperature: "{{ {'Zuluft': soll_zuluft, 'Raum': soll_raum}.get(regelungsart) }}"
    hvac_mode: "{{ 'heat' }}"
    min_temp: 10
    max_temp: 40
    temp_step: 0.5
    set_temperature:
      by: "{{ regelungsart }}"
      cases:
        Zuluft: {entity: soll_zuluft}
        Raum: {entity: soll_raum}
"""

# regelungsart=Zuluft, soll_zuluft=21.0, soll_raum=23.0, t_zuluft=20.0, t_raum=22.5
SWITCH_REGISTERS = {0: 2, 1: 210, 2: 230, 3: 200, 4: 225}


async def setup_switch_device(hass, monkeypatch):
    device = parse_device(yaml.safe_load(SWITCH_YAML), "hrv.yaml")
    client = FakeClient(dict(SWITCH_REGISTERS))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    return device, client, coordinator


async def _reselect(coordinator, client, register_value):
    """Change the regulation-type register and re-poll everything."""
    client.values[("holding", 0)] = register_value
    coordinator._next_due = dict.fromkeys(coordinator._next_due, 0.0)
    await coordinator.async_refresh()


async def test_climate_switch_target_follows_regulation_type(hass, monkeypatch):
    device, client, coordinator = await setup_switch_device(hass, monkeypatch)
    climate = make_entity(hass, ModbusConnectClimate, coordinator,
                          template_def(device, "klima"))

    # Zuluft selected -> the climate reads and writes the supply-air pair
    assert climate.current_temperature == pytest.approx(20.0)
    assert climate.target_temperature == pytest.approx(21.0)
    await climate.async_set_temperature(temperature=25.0)
    assert client.written[-1] == (1, [250])  # soll_zuluft, through its 0.1 codec
    assert climate.target_temperature == pytest.approx(25.0)

    # switch to Raum -> the same entity now follows the room pair, no reconfig
    await _reselect(coordinator, client, 3)
    assert climate.current_temperature == pytest.approx(22.5)
    assert climate.target_temperature == pytest.approx(23.0)
    await climate.async_set_temperature(temperature=24.0)
    assert client.written[-1] == (2, [240])  # soll_raum


async def test_climate_switch_target_unmatched_case_raises(hass, monkeypatch):
    device, client, coordinator = await setup_switch_device(hass, monkeypatch)
    climate = make_entity(hass, ModbusConnectClimate, coordinator,
                          template_def(device, "klima"))
    await _reselect(coordinator, client, 1)  # Abluft has no configured case
    with pytest.raises(ServiceValidationError):
        await climate.async_set_temperature(temperature=22.0)
    assert client.written == []  # nothing written when no case matches


# Device-info templates: firmware/hardware/serial composed from register values.
DEVICE_INFO_YAML = """
device:
  manufacturer: Acme
  model: HRV
  sw_version: "DSP {{ dsp | round(2) }} ARM {{ arm | round(2) }}"
  hw_version: "{{ hw_gen }}"
  serial_number: "{{ serial }}"
holding:
  dsp: {address: 0, multiplier: 0.01, internal: true}
  arm: {address: 1, multiplier: 0.01, internal: true}
  hw_gen: {address: 2, map: {4: Gen4}, internal: true}
  serial: {address: 3, type: string, count: 2, internal: true}
"""


async def setup_info_device(hass, monkeypatch, registers):
    device = parse_device(yaml.safe_load(DEVICE_INFO_YAML), "info.yaml")
    coordinator = await make_coordinator(hass, device, FakeClient(dict(registers)),
                                         monkeypatch, FakeTime())
    await coordinator.async_refresh()
    return coordinator


async def test_device_info_rendered_from_registers(hass, monkeypatch):
    # dsp=1.59, arm=1.57, hw_gen=Gen4, serial "SN42" (0x534E, 0x3432)
    coordinator = await setup_info_device(hass, monkeypatch,
                                          {0: 159, 1: 157, 2: 4, 3: 0x534E, 4: 0x3432})
    coordinator.apply_device_info()
    assert coordinator.device_info["sw_version"] == "DSP 1.59 ARM 1.57"
    assert coordinator.device_info["hw_version"] == "Gen4"
    assert coordinator.device_info["serial_number"] == "SN42"


async def test_device_info_skips_unread_register(hass, monkeypatch):
    # hw_gen register value 9 is not in the map -> decodes to None -> field skipped
    coordinator = await setup_info_device(hass, monkeypatch,
                                          {0: 159, 1: 157, 2: 9, 3: 0x534E, 4: 0x3432})
    coordinator.apply_device_info()
    assert coordinator.device_info["sw_version"] == "DSP 1.59 ARM 1.57"
    assert "hw_version" not in coordinator.device_info  # None render is not applied


async def test_solax_hybrid_bundled_device_info(hass, monkeypatch):
    """The shipped SolaX X3-Hybrid G4 file yields the real firmware/serial strings."""
    device = _load_file(BUILTIN_DIR / "Solax_X3_Hybrid_G4.yaml", "solax_x3_hybrid_g4.yaml")
    disp = "H34A10IA764696"  # byte-swapped in the registers (SolaX stores it swapped)
    raw = "".join(disp[i + 1] + disp[i] for i in range(0, len(disp), 2))
    regs = {i // 2: (ord(raw[i]) << 8) | ord(raw[i + 1]) for i in range(0, 14, 2)}  # serial @ 0-6
    regs[123], regs[124] = 159, 157  # firmware_dsp -> 1.59, firmware_arm -> 1.57
    coordinator = await make_coordinator(hass, device, FakeClient(regs), monkeypatch, FakeTime())
    await coordinator.async_refresh()
    coordinator.apply_device_info()
    assert coordinator.device_info["sw_version"] == "DSP 1.59 ARM 1.57"
    assert coordinator.device_info["hw_version"] == "Gen4"
    assert coordinator.device_info["serial_number"] == "H34A10IA764696"


async def test_solax_hybrid_writable_reads_via_readback(hass, monkeypatch):
    """A SolaX setting shows the value from its read-back register, and writes to its own."""
    device = _load_file(BUILTIN_DIR / "Solax_X3_Hybrid_G4.yaml", "solax_x3_hybrid_g4.yaml")
    by = {e.key: e for e in device.entities}
    # number: read-back reg 144 = 25.0 A (write reg 36 differs);
    # select: mppt read-back reg 188 = Enabled (write reg 72), map borrowed from the select
    client = FakeClient({144: 250, 36: 275, 188: 1})
    # exercise the whole config, not just the default 'basic' view
    coordinator = await make_coordinator(
        hass, device, client, monkeypatch, FakeTime(),
        options={OPTION_SHOW_ALL: True},
    )
    await coordinator.async_refresh()
    assert coordinator.data["battery_charge_max_current"] == pytest.approx(25.0)  # from reg 144
    assert coordinator.data["mppt"] == "Enabled"  # from reg 188, not its own write reg 72
    await coordinator.async_write(by["battery_charge_max_current"], 20.0)
    assert client.written == [(36, [200])]  # written to reg 36, the write register


async def test_solax_hybrid_computed_flow_sensors(hass, monkeypatch):
    """The rebuilt energy-flow templates split grid/battery power the way SolaX does."""
    from custom_components.modbus_connect import codec

    device = _load_file(BUILTIN_DIR / "Solax_X3_Hybrid_G4.yaml", "solax_x3_hybrid_g4.yaml")
    by = {e.key: e for e in device.entities}
    client = FakeClient()

    def put(key, value):  # round-trip through the entity's own codec into raw registers
        defn = by[key]
        for i, w in enumerate(codec.encode(defn, value)):
            client.values[(defn.table, defn.address + i)] = w & 0xFFFF

    put("inverter_power", 3000)
    put("measured_power", -800)         # grid: negative = importing 800 W
    put("battery_power_charge", -500)   # battery: negative = discharging 500 W
    put("battery_voltage_charge", 204.8)   # V
    put("bms_charge_max_current", 25.0)    # A -> charge ceiling 204.8 * 25 = 5120 W
    coordinator = await make_coordinator(
        hass, device, client, monkeypatch, FakeTime(),
        options={OPTION_SHOW_ALL: True},
    )
    await coordinator.async_refresh()

    def value(key):
        tdef = next(t for t in device.templates if t.key == key)
        return make_entity(hass, ModbusConnectTemplateSensor, coordinator, tdef).native_value

    assert coordinator.data["measured_power"] == -800  # int32 + swap: word round-trips
    assert value("grid_import") == 800                 # importing
    assert value("grid_export") == 0
    assert value("house_load") == 3800                 # inverter_power - measured_power
    assert value("battery_charge_power") == 0          # not charging
    assert value("battery_discharge_power") == 500     # discharging
    assert value("bms_max_charge") == 5120             # battery voltage x BMS max current


async def test_solax_hybrid_parallel_mode_split_per_inverter(hass, monkeypatch):
    """Parallel mode is split into a group per inverter (pm_i1/i2/i3). Enabling one
    inverter shows its own registers and the shared aggregates/count (which live in
    all three) but not another inverter's block or the advanced tier."""
    from custom_components.modbus_connect import codec

    device = _load_file(BUILTIN_DIR / "Solax_X3_Hybrid_G4.yaml", "solax_x3_hybrid_g4.yaml")
    by = {e.key: e for e in device.entities}

    # the split and the shared members (inverter-1 keys are unprefixed; the count
    # and the pm_total_* aggregates belong to the whole parallel system)
    assert by["pm_activepower_l1"].groups == ("pm_i1",)
    assert by["pm_i2_activepower_l1"].groups == ("pm_i2",)
    assert by["pm_inverter_count"].groups == ("pm_i1", "pm_i2", "pm_i3")
    totals = {t.key: t for t in device.templates}
    assert totals["pm_total_inverter_power"].groups == ("pm_i1", "pm_i2", "pm_i3")
    # the file overrides the switch labels the derive rule can't produce
    assert device.group_label("pm_i1") == "Parallel mode Inverter 1"
    assert device.group_label("pm_i3") == "Parallel mode Inverter 3"

    client = FakeClient()

    def put(key, value):  # round-trip through the entity's own codec into raw registers
        defn = by[key]
        for i, w in enumerate(codec.encode(defn, value)):
            client.values[(defn.table, defn.address + i)] = w & 0xFFFF

    put("pm_activepower_l1", 1500)
    put("pm_activepower_l2", 1200)
    put("pm_activepower_l3", -300)
    put("measured_power", 400)   # positive = exporting 400 W
    put("pm__current_l1", 6.5)   # int32 x0.1 A registers
    put("pm__current_l2", 5.2)
    put("pm__current_l3", 1.3)
    coordinator = await make_coordinator(
        hass, device, client, monkeypatch, FakeTime(),
        options={OPTION_ENABLED_GROUPS: ["pm_i1"]},
    )
    await coordinator.async_refresh()

    visible = {e.key for e in coordinator.visible_entities}
    assert "pm_activepower_l1" in visible                 # inverter 1 is on
    assert "pm_inverter_count" in visible                 # shared: in all three
    assert "pm_i2_activepower_l1" not in visible          # inverter 2 stays off
    assert "battery_charge_max_current" not in visible    # advanced stays off
    assert coordinator.data["pm_activepower_l1"] == 1500

    def value(key):
        tdef = next(t for t in device.templates if t.key == key)
        return make_entity(hass, ModbusConnectTemplateSensor, coordinator, tdef).native_value

    # the aggregates are visible under any inverter group and still compute
    assert value("pm_total_inverter_power") == 2400   # L1 + L2 + L3
    assert value("pm_total_house_load") == 2000       # PM power sum - grid power
    assert value("pm_total_inverter_current") == 13.0  # summed at 0.1 A resolution


async def test_solax_hybrid_energy_dashboard_groups(hass, monkeypatch):
    """The solar_details/home_consumption/grid_to_battery groups (upstream's Energy
    Dashboard switches) reveal the real entities plus the integral templates."""
    device = _load_file(BUILTIN_DIR / "Solax_X3_Hybrid_G4.yaml", "solax_x3_hybrid_g4.yaml")
    templates = {t.key: t for t in device.templates}

    # e_charge_today is promoted out of the expert tier into grid_to_battery
    # (and force-enabled: flipping that switch should show it immediately)
    e_charge = next(e for e in device.entities if e.key == "e_charge_today")
    assert e_charge.groups == ("grid_to_battery",)
    assert "entity_registry_enabled_default" not in e_charge.ha
    # house_load doubles as upstream's ED "Home Consumption Power"
    assert set(templates["house_load"].groups) == {"advanced", "home_consumption"}
    assert templates["grid_to_battery_power"].groups == ("grid_to_battery",)
    for key in ("pv_energy_1", "pv_energy_2", "home_consumption_energy"):
        assert templates[key].config["integrate"] == "trapezoidal"

    # enabling only home_consumption reveals its templates, not the advanced tier
    coordinator = await make_coordinator(
        hass, device, FakeClient({}), monkeypatch, FakeTime(),
        options={OPTION_ENABLED_GROUPS: ["home_consumption"]},
    )
    visible_templates = {t.key for t in coordinator.visible_templates}
    assert "house_load" in visible_templates
    assert "home_consumption_energy" in visible_templates
    assert "battery_charge_power" not in visible_templates  # advanced stays off
    assert "battery_charge_max_current" not in {e.key for e in coordinator.visible_entities}


async def test_solax_hybrid_grid_group(hass, monkeypatch):
    """The grid group reveals the per-phase V/I sensors and derives real power from
    them + the hidden power-factor registers: P = V x I x |PF| / 100, direction
    from the signed current, |PF| so a signed power factor can't double the sign."""
    from custom_components.modbus_connect import codec

    device = _load_file(BUILTIN_DIR / "Solax_X3_Hybrid_G4.yaml", "solax_x3_hybrid_g4.yaml")
    by = {e.key: e for e in device.entities}
    client = FakeClient()

    def put(key, value):  # round-trip through the entity's own codec into raw registers
        defn = by[key]
        for i, w in enumerate(codec.encode(defn, value)):
            client.values[(defn.table, defn.address + i)] = w & 0xFFFF

    for phase, (v, i, pf) in {
        1: (230.0, 10.0, 95),
        2: (231.0, 8.0, 90),
        # L3 exports (negative current) and reports a negative power factor: |PF|
        # keeps the sign coming from the current alone, so L3 reads -1145 W not +1145.
        3: (229.0, -5.0, -100),
    }.items():
        put(f"grid_voltage_l{phase}", v)
        put(f"grid_current_l{phase}", i)
        put(f"grid_power_factor_l{phase}", pf)

    # the 8 V/I entities are promoted into `grid` and force-enabled
    gv1 = by["grid_voltage_l1"]
    assert gv1.groups == ("grid",)
    assert "entity_registry_enabled_default" not in gv1.ha

    coordinator = await make_coordinator(
        hass, device, client, monkeypatch, FakeTime(),
        options={OPTION_ENABLED_GROUPS: ["grid"]},
    )
    await coordinator.async_refresh()

    visible = {e.key for e in coordinator.visible_entities}
    assert {"grid_voltage", "grid_voltage_l1", "grid_current_total", "grid_current_l3"} <= visible
    assert "battery_charge_max_current" not in visible  # advanced stays off
    # the power-factor registers stay hidden but are polled to feed the templates
    assert "grid_power_factor_l1" not in visible
    assert coordinator.data["grid_power_factor_l1"] == 95

    def value(key):
        tdef = next(t for t in device.templates if t.key == key)
        return make_entity(hass, ModbusConnectTemplateSensor, coordinator, tdef).native_value

    assert value("grid_power_l1") == 2185   # 230 x 10 x 0.95
    assert value("grid_power_l2") == 1663   # 231 x 8 x 0.90 -> 1663.2
    assert value("grid_power_l3") == -1145  # 229 x -5 x abs(-1.00) (export)
    assert value("grid_power") == 2703      # sum of the three phases


async def test_bms_max_charge_falls_back_when_bms_current_missing(hass, monkeypatch):
    """bms_max_charge falls back to the settable charge limit when the BMS current
    sensor reads as None (mirrors SolaX value_function_bms_max_charge)."""
    doc = yaml.safe_load(
        """
device: {manufacturer: T, model: BMS, max_register_read: 100, max_read_gap: 8}
holding:
  battery_voltage_charge: {address: 0, multiplier: 0.1, ha: {platform: sensor}}
  bms_charge_max_current: {address: 100, multiplier: 0.1, ha: {platform: sensor}}
  battery_charge_max_current: {address: 200, multiplier: 0.1, ha: {platform: sensor}}
template:
  bms_max_charge:
    ha: {platform: sensor}
    state: "{{ ((battery_voltage_charge or 0) * (bms_charge_max_current if bms_charge_max_current is not none else (battery_charge_max_current or 20))) | int }}"
"""
    )
    device = parse_device(doc, "bms.yaml")
    client = FakeClient({0: 2048, 200: 300})  # 204.8 V; fallback limit 30.0 A
    client.fail_addresses.add(100)  # BMS current sensor unreadable -> decodes to None
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    await coordinator.async_refresh()
    assert coordinator.data["bms_charge_max_current"] is None  # its own block failed
    tdef = next(t for t in device.templates if t.key == "bms_max_charge")
    entity = make_entity(hass, ModbusConnectTemplateSensor, coordinator, tdef)
    assert entity.native_value == 6144  # 204.8 V x 30.0 A fallback limit


def _integral_device(state='"{{ [p or 0, 0] | max }}"', method="trapezoidal"):
    return parse_device(
        yaml.safe_load(
            f"""
device: {{manufacturer: T, model: E}}
holding:
  p: {{address: 0, ha: {{platform: sensor}}}}
template:
  e:
    state: {state}
    integrate: {method}
    ha: {{platform: sensor, device_class: energy, state_class: total_increasing,
         unit_of_measurement: kWh}}
"""
        ),
        "e.yaml",
    )


async def test_integral_sensor_accumulates_watts_into_kwh(hass, monkeypatch):
    """`integrate: trapezoidal` sums rendered watts over every refresh — a
    refresh the coordinator suppresses as unchanged (always_update=False skips
    the listeners) still samples through the per-refresh hook, so a constant
    plateau is credited at its constant power, not averaged into the next step."""
    device = _integral_device()
    client = FakeClient({0: 600})
    faketime = FakeTime()
    coordinator = await make_coordinator(hass, device, client, monkeypatch, faketime)
    await coordinator.async_refresh()

    entity = make_entity(hass, ModbusConnectIntegralSensor, coordinator, device.templates[0])
    entity.async_write_ha_state = lambda: None  # not registered with a platform
    unsub_listener = coordinator.async_add_listener(entity._handle_coordinator_update)
    unsub_refresh = coordinator.async_add_refresh_callback(entity._on_refresh)
    entity._advance(coordinator.data)  # the seeding async_added_to_hass does
    assert entity.native_value == 0.0

    faketime.now += 300  # 600 W ramping to 400 W over 5 min -> 500 W avg
    client.values[("holding", 0)] = 400
    await coordinator.async_refresh()
    assert entity.native_value == pytest.approx(500 * 300 / 3_600_000, abs=1e-3)

    faketime.now += 300  # unchanged data: the hook still samples 400 W flat
    await coordinator.async_refresh()
    assert entity.native_value == pytest.approx(0.075)  # 0.0417 + 400 W x 300 s

    faketime.now += 300  # the drop to 0 only shapes its own 5-min interval
    client.values[("holding", 0)] = 0
    await coordinator.async_refresh()
    assert entity.native_value == pytest.approx(0.092)  # + 200 W x 300 s, 3-digit display
    unsub_listener()
    unsub_refresh()


async def test_integral_sensor_methods_and_gaps(hass, monkeypatch):
    """left/right rectangles pick the matching endpoint; an outage (failed
    refresh) drops the open interval instead of interpolating across it."""
    for method, expected in (("left", 600.0), ("right", 200.0)):
        device = _integral_device(state='"{{ p }}"', method=method)
        client = FakeClient({0: 600})
        faketime = FakeTime()
        coordinator = await make_coordinator(hass, device, client, monkeypatch, faketime)
        await coordinator.async_refresh()
        entity = make_entity(
            hass, ModbusConnectIntegralSensor, coordinator, device.templates[0]
        )
        entity.async_write_ha_state = lambda: None  # not registered with a platform
        unsub_listener = coordinator.async_add_listener(entity._handle_coordinator_update)
        unsub_refresh = coordinator.async_add_refresh_callback(entity._on_refresh)
        entity._advance(coordinator.data)  # seed

        faketime.now += 3600  # one hour 600 W -> 200 W
        client.values[("holding", 0)] = 200
        await coordinator.async_refresh()
        assert entity.native_value == pytest.approx(expected / 1000)  # Wh -> kWh

        client.fail_addresses.add(0)  # whole refresh fails: the listener sees the
        faketime.now += 3600          # failure and drops the open interval
        await coordinator.async_refresh()
        assert entity.native_value == pytest.approx(expected / 1000)  # unchanged

        client.fail_addresses.clear()  # recovery seeds a fresh sample point:
        client.values[("holding", 0)] = 500  # the unreadable hour is skipped entirely
        faketime.now += 3600
        await coordinator.async_refresh()
        assert entity.native_value == pytest.approx(expected / 1000)
        unsub_listener()
        unsub_refresh()


# --- key() template helper: compare enums by stable map key, not by label ------

KEY_YAML = """
translations:
  "Off": {en: "Off", de: "Aus"}
  "Auto": {en: "Auto", de: "Automatik"}
device:
  manufacturer: Acme
  model: HeatPump
holding:
  mode:
    address: 0
    map: {0: "Off", 1: "Auto"}
    ha: {platform: select}
  power:
    address: 1
    ha: {platform: sensor}
template:
  raw_mode:
    ha: {platform: sensor}
    state: "{{ key('mode') }}"
  is_auto:
    ha: {platform: sensor}
    state: "{{ 'yes' if key('mode') == 1 else 'no' }}"
  raw_power:
    ha: {platform: sensor}
    state: "{{ key('power') }}"
"""


async def _key_setup(hass, monkeypatch, language):
    device = parse_device(yaml.safe_load(KEY_YAML), "key.yaml", language=language)
    client = FakeClient({0: 1, 1: 250})  # mode = register 1 = "Auto", power = 250
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    return device, coordinator


async def test_key_helper_returns_raw_map_key(hass, monkeypatch):
    device, coordinator = await _key_setup(hass, monkeypatch, "en")
    assert coordinator.data["mode"] == "Auto"  # the decoded display label
    raw = make_entity(hass, ModbusConnectTemplateSensor, coordinator,
                      template_def(device, "raw_mode"))
    is_auto = make_entity(hass, ModbusConnectTemplateSensor, coordinator,
                          template_def(device, "is_auto"))
    passthrough = make_entity(hass, ModbusConnectTemplateSensor, coordinator,
                              template_def(device, "raw_power"))
    assert raw.native_value == 1  # the map key behind "Auto", not the label
    assert is_auto.native_value == "yes"
    assert passthrough.native_value == 250  # non-mapped entity: its plain value


async def test_key_helper_is_language_independent(hass, monkeypatch):
    device, coordinator = await _key_setup(hass, monkeypatch, "de")
    assert coordinator.data["mode"] == "Automatik"  # label is translated ...
    raw = make_entity(hass, ModbusConnectTemplateSensor, coordinator,
                      template_def(device, "raw_mode"))
    is_auto = make_entity(hass, ModbusConnectTemplateSensor, coordinator,
                          template_def(device, "is_auto"))
    assert raw.native_value == 1  # ... but the key is unchanged, so
    assert is_auto.native_value == "yes"  # key('mode') == 1 still holds under de


async def test_fan_read_only_templates_enable_features(hass, monkeypatch):
    """percentage/preset_mode state templates must set SET_SPEED/PRESET_MODE —
    HA only exposes those attributes behind the feature flags, so without them
    a read-only template would be silently invisible (light.py's brightness
    already follows this template-or-action pattern)."""
    from homeassistant.components.fan import FanEntityFeature

    device = parse_device(
        yaml.safe_load(
            """
device: {manufacturer: T, model: F}
holding:
  stage: {address: 0, internal: true}
template:
  vent:
    ha: {platform: fan}
    state: "{{ stage > 0 }}"
    percentage: "{{ stage * 25 }}"
    preset_mode: "{{ 'auto' }}"
    preset_modes: [auto, manual]
    turn_on: {entity: stage, value: 1}
    turn_off: {entity: stage, value: 0}
"""
        ),
        "f.yaml",
    )
    client = FakeClient({0: 2})
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    await coordinator.async_refresh()
    fan = make_entity(hass, ModbusConnectFan, coordinator, device.templates[0])
    assert FanEntityFeature.SET_SPEED in fan.supported_features
    assert FanEntityFeature.PRESET_MODE in fan.supported_features
    assert fan.percentage == 50
    assert fan.preset_mode == "auto"
    # setting without the action still fails with the clean "no action" error
    with pytest.raises(ServiceValidationError, match="set_percentage"):
        await fan.async_set_percentage(40)
