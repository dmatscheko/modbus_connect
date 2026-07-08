"""Runtime tests for template: entities."""

import pytest
import yaml
from homeassistant.components.climate import HVACMode

from custom_components.modbus_connect.binary_sensor import ModbusConnectTemplateBinarySensor
from custom_components.modbus_connect.climate import ModbusConnectClimate
from custom_components.modbus_connect.cover import ModbusConnectCover
from custom_components.modbus_connect.entity import build_template_description
from custom_components.modbus_connect.fan import ModbusConnectFan
from custom_components.modbus_connect.light import ModbusConnectLight
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
