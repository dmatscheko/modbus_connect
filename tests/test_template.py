"""Runtime tests for template: entities."""

import pytest
import yaml
from homeassistant.components.climate import HVACMode
from homeassistant.exceptions import ServiceValidationError

from custom_components.modbus_connect.binary_sensor import ModbusConnectTemplateBinarySensor
from custom_components.modbus_connect.climate import ModbusConnectClimate
from custom_components.modbus_connect.const import OPTION_ENABLED_GROUPS
from custom_components.modbus_connect.cover import ModbusConnectCover
from custom_components.modbus_connect.entity import build_template_description
from custom_components.modbus_connect.fan import ModbusConnectFan
from custom_components.modbus_connect.light import ModbusConnectLight
from custom_components.modbus_connect.loader import BUILTIN_DIR, _load_file
from custom_components.modbus_connect.number import ModbusConnectTemplateNumber
from custom_components.modbus_connect.schema import parse_device
from custom_components.modbus_connect.select import ModbusConnectTemplateSelect
from custom_components.modbus_connect.sensor import ModbusConnectTemplateSensor
from custom_components.modbus_connect.switch import ModbusConnectTemplateSwitch

from .test_coordinator import FakeClient, FakeTime, make_coordinator

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

    client.registers[0] = 100  # 10.0 degrees
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
    client.registers[0] = register_value
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
        options={OPTION_ENABLED_GROUPS: ["all"]},
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
    regs: dict[int, int] = {}

    def put(key, value):  # round-trip through the entity's own codec into raw registers
        defn = by[key]
        for i, w in enumerate(codec.encode(defn, value)):
            regs[defn.address + i] = w & 0xFFFF

    put("inverter_power", 3000)
    put("measured_power", -800)         # grid: negative = importing 800 W
    put("battery_power_charge", -500)   # battery: negative = discharging 500 W
    put("battery_voltage_charge", 204.8)   # V
    put("bms_charge_max_current", 25.0)    # A -> charge ceiling 204.8 * 25 = 5120 W
    coordinator = await make_coordinator(
        hass, device, FakeClient(regs), monkeypatch, FakeTime(),
        options={OPTION_ENABLED_GROUPS: ["all"]},
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
