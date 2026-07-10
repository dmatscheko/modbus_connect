"""Integration setup, platform, write, and diagnostics tests with a fake client."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.modbus_connect.client import ModbusBlockClient
from custom_components.modbus_connect.const import (
    CONF_FILENAME,
    CONF_PREFIX,
    CONF_SLAVE_ID,
    DOMAIN,
    OPTION_ENABLED_GROUPS,
    OPTION_MIN_SCAN_INTERVAL,
    OPTION_SHOW_ALL,
)
from custom_components.modbus_connect.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.modbus_connect.models import BIT_TABLES, Span

DEVICE_YAML = """
device:
  manufacturer: Acme
  model: X1
holding:
  temperature:
    address: 0
    multiplier: 0.1
    ha:
      platform: sensor
      name: Temperature
      unit_of_measurement: "°C"
  setpoint:
    address: 1
    duplicate_as_sensor: true
    ha:
      platform: number
      name: Setpoint
      min: 0
      max: 255
  mode:
    address: 2
    map: {0: "Off", 1: "Auto"}
    ha:
      platform: select
      name: Mode
  label:
    address: 3
    type: string
    count: 2
    ha:
      platform: text
      name: Label
  reset:
    address: 5
    write_value: 1
    ha:
      platform: button
      name: Reset
  power:
    address: 4
    on_value: 5
    off_value: 6
    ha:
      platform: switch
      name: Power
  valve:
    address: 6
    ha:
      platform: switch
      name: Valve
  status:
    address: 7
    map: {0: "ok", 1: "warn"}
    ha:
      platform: sensor
      name: Status
  schedule:
    address: 8
    type: time
    ha:
      platform: time
      name: Schedule
  schedule_unset:
    address: 9
    type: time
    ha:
      platform: time
      name: Schedule unset
  schedule_rectified:
    address: 10
    type: time
    rectify_time: true
    ha:
      platform: time
      name: Schedule rectified
coil:
  pump:
    address: 0
    ha:
      platform: switch
      name: Pump
discrete:
  alarm:
    address: 1
    ha:
      platform: binary_sensor
      name: Alarm
template:
  double_temp:
    state: "{{ temperature * 2 }}"
    ha:
      platform: sensor
      name: Double temp
  t_switch:
    state: "{{ pump }}"
    turn_on: {entity: pump, value: 1}
    turn_off: {entity: pump, value: 0}
    ha:
      platform: switch
      name: T switch
  t_number:
    state: "{{ setpoint }}"
    set_value: {entity: setpoint}
    ha:
      platform: number
      name: T number
      min: 0
      max: 255
  t_select:
    state: "{{ mode }}"
    select_option: {entity: mode}
    ha:
      platform: select
      name: T select
  t_light:
    state: "{{ pump }}"
    brightness: "{{ setpoint }}"
    turn_on: {entity: pump, value: 1}
    turn_off: {entity: pump, value: 0}
    set_brightness: {entity: setpoint}
    ha:
      platform: light
      name: T light
  t_fan:
    state: "{{ pump }}"
    percentage: "{{ setpoint }}"
    preset_mode: "{{ 'eco' }}"
    turn_on: {entity: pump, value: 1}
    turn_off: {entity: pump, value: 0}
    set_percentage: {entity: setpoint}
    set_preset_mode:
      entity: setpoint
      map: {eco: 10, boost: 90}
    ha:
      platform: fan
      name: T fan
  t_cover:
    position: "{{ setpoint }}"
    open_cover: {entity: pump, value: 1}
    close_cover: {entity: pump, value: 0}
    set_position: {entity: setpoint}
    ha:
      platform: cover
      name: T cover
  t_climate:
    current_temperature: "{{ temperature }}"
    target_temperature: "{{ setpoint }}"
    hvac_mode: "{{ 'heat' if mode == 'Auto' else 'off' }}"
    min_temp: 5
    max_temp: 95
    temp_step: 0.5
    set_temperature: {entity: setpoint}
    set_hvac_mode:
      entity: mode
      map: {heat: "Auto", "off": "Off"}
    ha:
      platform: climate
      name: T climate
  t_climate2:
    current_temperature: "{{ temperature }}"
    hvac_mode: "{{ 'banana' }}"
    hvac_action: "{{ 'banana' }}"
    ha:
      platform: climate
      name: T climate2
  t_cover2:
    is_closed: "{{ not pump }}"
    open_cover: {entity: pump, value: 1}
    close_cover: {entity: pump, value: 0}
    stop_cover: {entity: pump, value: 0}
    ha:
      platform: cover
      name: T cover2
  t_select2:
    state: "{{ 'A' }}"
    options: ["A", "B"]
    select_option:
      entity: setpoint
      map: {A: 1}
    ha:
      platform: select
      name: T select2
  t_bad:
    state: "{{ this_does_not_exist + 1 }}"
    ha:
      platform: sensor
      name: T bad
  t_list:
    state: "{{ [1, 2] }}"
    ha:
      platform: sensor
      name: T list
"""


class FakeClient:
    """Duck-typed ModbusBlockClient backed by a dict."""

    target = "192.0.2.1:502"

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.values: dict[tuple[str, int], int | bool] = {
            ("holding", 0): 215,  # temperature 21.5
            ("holding", 1): 42,  # setpoint
            ("holding", 2): 1,  # mode "Auto"
            ("holding", 3): 0x6869,  # "hi"
            ("holding", 4): 5,  # power "on" (custom on/off values 5/6)
            ("holding", 5): 0,
            ("holding", 6): 1,  # valve on
            ("holding", 7): 9,  # status: not in the map -> undecodable
            ("holding", 8): 3102,  # schedule: 12*256 + 30 -> 12:30
            ("holding", 9): 0x1800,  # schedule_unset: 24:00, no rectify -> unavailable
            ("holding", 10): 0x1800,  # schedule_rectified: 24:00 -> 23:59
            ("coil", 0): True,  # pump on
            ("discrete", 1): True,  # alarm on
        }
        self.released: list[str] = []
        self.connected_ok = True

    async def ensure_connected(self) -> bool:
        return self.connected_ok

    async def read_block(self, device_id: int, span: Span) -> list[int] | list[bool]:
        default: int | bool = False if span.table in BIT_TABLES else 0
        return [
            self.values.get((span.table, a), default)
            for a in range(span.start, span.end)
        ]

    async def write_registers(
        self, device_id: int, address: int, words: list[int], *, multiple: bool = False
    ) -> None:
        for i, word in enumerate(words):
            self.values[("holding", address + i)] = word

    async def write_coil(self, device_id: int, address: int, value: bool) -> None:
        self.values[("coil", address)] = value

    def release(self, entry_id: str) -> None:
        self.released.append(entry_id)


def write_device_file(hass: HomeAssistant) -> None:
    directory = Path(hass.config.config_dir) / DOMAIN
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "acme_x1.yaml").write_text(DEVICE_YAML, encoding="utf-8")


def make_entry(filename: str = "acme_x1.yaml") -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.0.2.1",
            "port": 502,
            CONF_SLAVE_ID: 7,
            CONF_FILENAME: filename,
        },
        unique_id="192.0.2.1:502:7",
        title="Acme X1",
    )


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry, client: FakeClient) -> bool:
    write_device_file(hass)
    entry.add_to_hass(hass)
    with patch.object(ModbusBlockClient, "acquire", return_value=client):
        ok = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return ok


def eid(hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str) -> str:
    """Resolve the entity id for a device-file key via the entity registry."""
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{entry.entry_id}_{key}"
    )
    assert entity_id is not None, f"{platform}/{key} not registered"
    return entity_id


async def test_connection_tuning_reaches_the_client(hass: HomeAssistant) -> None:
    directory = Path(hass.config.config_dir) / DOMAIN
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "tuned.yaml").write_text(
        DEVICE_YAML.replace(
            "model: X1",
            "model: X1\n  timeout: 5\n  retries: 3\n  request_delay: 0.05",
        ),
        encoding="utf-8",
    )
    entry = make_entry("tuned.yaml")
    entry.add_to_hass(hass)
    with patch.object(
        ModbusBlockClient, "acquire", return_value=FakeClient()
    ) as acquire:
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert acquire.call_args.kwargs["timeout"] == 5
    assert acquire.call_args.kwargs["retries"] == 3
    assert acquire.call_args.kwargs["request_delay"] == pytest.approx(0.05)


async def test_valve_platform(hass: HomeAssistant) -> None:
    directory = Path(hass.config.config_dir) / DOMAIN
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "valves.yaml").write_text(
        """
device:
  manufacturer: Acme
  model: V1
holding:
  ball_valve:
    address: 20
    on_value: 2
    off_value: 3
    ha:
      platform: valve
      name: Ball valve
      device_class: water
  mix_valve:
    address: 21
    ha:
      platform: valve
      name: Mix valve
      reports_position: true
""",
        encoding="utf-8",
    )
    client = FakeClient()
    client.values[("holding", 20)] = 2  # ball valve: custom on_value -> open
    client.values[("holding", 21)] = 40  # mixer at 40 %
    entry = make_entry("valves.yaml")
    entry.add_to_hass(hass)
    with patch.object(ModbusBlockClient, "acquire", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ball = eid(hass, entry, "valve", "ball_valve")
    mix = eid(hass, entry, "valve", "mix_valve")
    assert hass.states.get(ball).state == "open"
    mix_state = hass.states.get(mix)
    assert mix_state.state == "open"
    assert mix_state.attributes["current_position"] == 40

    # binary valve: close writes the configured off_value
    await hass.services.async_call(
        "valve", "close_valve", {"entity_id": ball}, blocking=True
    )
    assert client.values[("holding", 20)] == 3
    assert hass.states.get(ball).state == "closed"

    # position valve: set_position writes the percentage, open/close the ends
    await hass.services.async_call(
        "valve",
        "set_valve_position",
        {"entity_id": mix, "position": 75},
        blocking=True,
    )
    assert client.values[("holding", 21)] == 75
    await hass.services.async_call(
        "valve", "close_valve", {"entity_id": mix}, blocking=True
    )
    assert client.values[("holding", 21)] == 0
    assert hass.states.get(mix).state == "closed"
    await hass.services.async_call(
        "valve", "open_valve", {"entity_id": mix}, blocking=True
    )
    assert client.values[("holding", 21)] == 100


async def test_serial_entry_uses_serial_client(hass: HomeAssistant) -> None:
    write_device_file(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "serial_port": "/dev/ttyUSB0",
            "baudrate": 19200,
            "bytesize": 8,
            "parity": "E",
            "stopbits": 1,
            CONF_SLAVE_ID: 7,
            CONF_FILENAME: "acme_x1.yaml",
        },
        unique_id="/dev/ttyUSB0:7",
        title="Acme X1",
    )
    entry.add_to_hass(hass)
    with patch.object(
        ModbusBlockClient, "acquire_serial", return_value=FakeClient()
    ) as acquire:
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert acquire.call_args.args[0] == "/dev/ttyUSB0"
    assert acquire.call_args.kwargs["baudrate"] == 19200
    assert acquire.call_args.kwargs["parity"] == "E"
    # the connection shows on the device card via model_id
    device = dr.async_get(hass).async_get_device({(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.model_id == "/dev/ttyUSB0 · ID 7"


async def test_setup_creates_all_platform_entities(hass: HomeAssistant) -> None:
    entry = make_entry()
    assert await setup_entry(hass, entry, FakeClient())
    assert entry.state is ConfigEntryState.LOADED

    for platform, key, expected in [
        ("sensor", "temperature", "21.5"),
        ("number", "setpoint", "42"),
        ("select", "mode", "Auto"),
        ("text", "label", "hi"),
        ("switch", "pump", "on"),
        ("binary_sensor", "alarm", "on"),
        ("sensor", "double_temp", "43.0"),
        ("switch", "t_switch", "on"),
        ("number", "t_number", "42.0"),
        ("select", "t_select", "Auto"),
        ("light", "t_light", "on"),
        ("fan", "t_fan", "on"),
        ("cover", "t_cover", "open"),
        ("climate", "t_climate", "heat"),
        ("time", "schedule", "12:30:00"),
        ("time", "schedule_rectified", "23:59:00"),  # 24:00 rectified to end of day
        ("time", "schedule_unset", "unavailable"),  # 24:00 without rectify_time drops out
    ]:
        state = hass.states.get(eid(hass, entry, platform, key))
        assert state is not None, f"{platform}/{key} has no state"
        assert state.state == expected, f"{platform}/{key}: {state.state} != {expected}"

    # duplicate_as_sensor mirror of the setpoint number
    mirror = hass.states.get(eid(hass, entry, "sensor", "setpoint_sensor"))
    assert mirror is not None
    assert mirror.state == "42"

    # integration-level diagnostic: one reads-per-refresh sensor per device
    reads = hass.states.get(eid(hass, entry, "sensor", "reads_per_refresh"))
    assert reads is not None
    assert int(reads.state) >= 1  # a full refresh needs at least one block read
    # block merging: reads never exceed the entities they cover
    assert reads.attributes["read_entities"] >= int(reads.state)
    # per-cycle count lives in Download Diagnostics, not as a churning attribute
    assert "polled_entities" not in reads.attributes
    # diagnostic gauge -> no long-term statistics
    assert "state_class" not in reads.attributes


async def test_unload_releases_client(hass: HomeAssistant) -> None:
    entry = make_entry()
    client = FakeClient()
    assert await setup_entry(hass, entry, client)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert client.released == [entry.entry_id]


async def test_setup_missing_device_file(hass: HomeAssistant) -> None:
    entry = make_entry(filename="does_not_exist.yaml")
    assert not await setup_entry(hass, entry, FakeClient())
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_retry_when_gateway_down(hass: HomeAssistant) -> None:
    entry = make_entry()
    client = FakeClient()
    client.connected_ok = False
    assert not await setup_entry(hass, entry, client)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    # the failed setup must not leak a client reference
    assert client.released == [entry.entry_id]
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()


async def test_writes_through_entities(hass: HomeAssistant) -> None:
    entry = make_entry()
    client = FakeClient()
    assert await setup_entry(hass, entry, client)

    # number: multiplier-free write, confirmed by read-back
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": eid(hass, entry, "number", "setpoint"), "value": 100},
        blocking=True,
    )
    assert client.values[("holding", 1)] == 100
    assert hass.states.get(eid(hass, entry, "number", "setpoint")).state == "100"

    # select: mapped write
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": eid(hass, entry, "select", "mode"), "option": "Off"},
        blocking=True,
    )
    assert client.values[("holding", 2)] == 0

    # switch on a coil
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": eid(hass, entry, "switch", "pump")},
        blocking=True,
    )
    assert client.values[("coil", 0)] is False

    # text
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": eid(hass, entry, "text", "label"), "value": "ok"},
        blocking=True,
    )
    assert client.values[("holding", 3)] == 0x6F6B  # "ok"

    # button writes its fixed value
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": eid(hass, entry, "button", "reset")},
        blocking=True,
    )
    assert client.values[("holding", 5)] == 1


async def test_template_actions(hass: HomeAssistant) -> None:
    entry = make_entry()
    client = FakeClient()
    assert await setup_entry(hass, entry, client)

    # template switch writes through to the coil
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": eid(hass, entry, "switch", "t_switch")},
        blocking=True,
    )
    assert client.values[("coil", 0)] == 0

    # template light: brightness goes to the mapped holding register
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": eid(hass, entry, "light", "t_light"), "brightness": 128},
        blocking=True,
    )
    assert client.values[("holding", 1)] == 128

    # template fan: percentage 0 routes to turn_off
    await hass.services.async_call(
        "fan",
        "set_percentage",
        {"entity_id": eid(hass, entry, "fan", "t_fan"), "percentage": 0},
        blocking=True,
    )
    assert client.values[("coil", 0)] == 0

    # template cover: set_position writes the register
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": eid(hass, entry, "cover", "t_cover"), "position": 75},
        blocking=True,
    )
    assert client.values[("holding", 1)] == 75

    # template climate: temperature and hvac mode (mapped)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": eid(hass, entry, "climate", "t_climate"), "temperature": 55},
        blocking=True,
    )
    assert client.values[("holding", 1)] == 55
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": eid(hass, entry, "climate", "t_climate"), "hvac_mode": "off"},
        blocking=True,
    )
    assert client.values[("holding", 2)] == 0


async def test_options_update_reloads_entry(hass: HomeAssistant) -> None:
    entry = make_entry()
    client = FakeClient()
    write_device_file(hass)
    entry.add_to_hass(hass)
    with patch.object(ModbusBlockClient, "acquire", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # the option is a floor above the device default, so it raises the interval
        hass.config_entries.async_update_entry(
            entry, options={OPTION_MIN_SCAN_INTERVAL: 120}
        )
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.update_interval.total_seconds() == pytest.approx(120)


async def test_diagnostics(hass: HomeAssistant) -> None:
    entry = make_entry()
    assert await setup_entry(hass, entry, FakeClient())

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["entry"]["data"]["host"] == "**REDACTED**"
    assert diagnostics["device"]["manufacturer"] == "Acme"
    assert diagnostics["device"]["model"] == "X1"
    assert diagnostics["polling"]["last_update_success"] is True
    by_key = {e["key"]: e for e in diagnostics["entities"]}
    assert by_key["temperature"]["value"] == pytest.approx(21.5)
    assert by_key["temperature"]["address"] == 0
    assert {t["key"] for t in diagnostics["templates"]} >= {"double_temp", "t_climate"}


async def test_switch_variants_and_undecodable_value(hass: HomeAssistant) -> None:
    entry = make_entry()
    client = FakeClient()
    assert await setup_entry(hass, entry, client)

    # configured on/off raw values on a holding register
    power = eid(hass, entry, "switch", "power")
    assert hass.states.get(power).state == "on"
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": power}, blocking=True
    )
    assert client.values[("holding", 4)] == 6
    assert hass.states.get(power).state == "off"
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": power}, blocking=True
    )
    assert client.values[("holding", 4)] == 5

    # default 1/0 payloads on a holding register
    valve = eid(hass, entry, "switch", "valve")
    assert hass.states.get(valve).state == "on"
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": valve}, blocking=True
    )
    assert client.values[("holding", 6)] == 0

    # a register value missing from the map decodes to None -> unavailable
    assert hass.states.get(eid(hass, entry, "sensor", "status")).state == "unavailable"


async def test_template_edge_rendering(hass: HomeAssistant) -> None:
    entry = make_entry()
    assert await setup_entry(hass, entry, FakeClient())

    # failing template -> unknown, not an exception
    assert hass.states.get(eid(hass, entry, "sensor", "t_bad")).state == "unknown"
    # non-primitive template results are stringified
    assert hass.states.get(eid(hass, entry, "sensor", "t_list")).state == "[1, 2]"
    # invalid hvac_mode/hvac_action strings are dropped
    assert hass.states.get(eid(hass, entry, "climate", "t_climate2")).state == "unknown"
    # is_closed template: pump is on -> not closed
    assert hass.states.get(eid(hass, entry, "cover", "t_cover2")).state == "open"
    # preset comes from the template
    fan = hass.states.get(eid(hass, entry, "fan", "t_fan"))
    assert fan.attributes["preset_mode"] == "eco"
    assert fan.attributes["preset_modes"] == ["eco", "boost"]


async def test_more_template_actions(hass: HomeAssistant) -> None:
    entry = make_entry()
    client = FakeClient()
    assert await setup_entry(hass, entry, client)

    # fan: turn_on with a percentage writes both actions
    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": eid(hass, entry, "fan", "t_fan"), "percentage": 60},
        blocking=True,
    )
    assert client.values[("coil", 0)] == 1
    assert client.values[("holding", 1)] == 60

    # fan: preset mode goes through its map
    await hass.services.async_call(
        "fan",
        "set_preset_mode",
        {"entity_id": eid(hass, entry, "fan", "t_fan"), "preset_mode": "boost"},
        blocking=True,
    )
    assert client.values[("holding", 1)] == 90

    # climate turn_off / turn_on write the mapped mode values
    climate = eid(hass, entry, "climate", "t_climate")
    await hass.services.async_call(
        "climate", "turn_off", {"entity_id": climate}, blocking=True
    )
    assert client.values[("holding", 2)] == 0
    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": climate}, blocking=True
    )
    assert client.values[("holding", 2)] == 1

    # cover open/close/stop (fixed actions)
    cover = eid(hass, entry, "cover", "t_cover2")
    await hass.services.async_call(
        "cover", "close_cover", {"entity_id": cover}, blocking=True
    )
    assert client.values[("coil", 0)] == 0
    await hass.services.async_call(
        "cover", "open_cover", {"entity_id": cover}, blocking=True
    )
    assert client.values[("coil", 0)] == 1
    await hass.services.async_call(
        "cover", "stop_cover", {"entity_id": cover}, blocking=True
    )
    assert client.values[("coil", 0)] == 0

    # light turn_off
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": eid(hass, entry, "light", "t_light")},
        blocking=True,
    )
    assert client.values[("coil", 0)] == 0


async def test_unmapped_action_value_raises(hass: HomeAssistant) -> None:
    from homeassistant.exceptions import ServiceValidationError

    entry = make_entry()
    client = FakeClient()
    assert await setup_entry(hass, entry, client)

    # "A" is mapped and writes; "B" is a valid option without a mapping
    select = eid(hass, entry, "select", "t_select2")
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": select, "option": "A"},
        blocking=True,
    )
    assert client.values[("holding", 1)] == 1

    with pytest.raises(ServiceValidationError, match="no 'select_option' mapping"):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": select, "option": "B"},
            blocking=True,
        )


async def test_write_failure_becomes_home_assistant_error(hass: HomeAssistant) -> None:
    from homeassistant.exceptions import HomeAssistantError

    entry = make_entry()
    client = FakeClient()
    assert await setup_entry(hass, entry, client)

    client.connected_ok = False
    with pytest.raises(HomeAssistantError, match="Cannot connect"):
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": eid(hass, entry, "number", "setpoint"), "value": 1},
            blocking=True,
        )


async def test_prefix_drives_entity_ids(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.0.2.1",
            "port": 502,
            CONF_SLAVE_ID: 7,
            CONF_FILENAME: "acme_x1.yaml",
            CONF_NAME: "Heat pump",
            CONF_PREFIX: "hp",
        },
        unique_id="192.0.2.1:502:7",
        title="Heat pump",
    )
    assert await setup_entry(hass, entry, FakeClient())

    assert eid(hass, entry, "sensor", "temperature") == "sensor.hp_temperature"
    assert eid(hass, entry, "number", "setpoint") == "number.hp_setpoint"
    # the duplicate_as_sensor mirror keeps its suffix
    assert eid(hass, entry, "sensor", "setpoint_sensor") == "sensor.hp_setpoint_sensor"
    # template entities are prefixed too
    assert eid(hass, entry, "sensor", "double_temp") == "sensor.hp_double_temp"
    assert eid(hass, entry, "climate", "t_climate") == "climate.hp_t_climate"

    # the device name comes from the name, not the prefix
    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, entry.entry_id)}
    )
    assert device is not None
    assert device.name == "Heat pump"


async def test_no_prefix_keeps_device_name_entity_ids(hass: HomeAssistant) -> None:
    entry = make_entry()  # no prefix, no name
    assert await setup_entry(hass, entry, FakeClient())
    # default HA naming: device name (manufacturer + model) + entity name
    assert eid(hass, entry, "sensor", "temperature") == "sensor.acme_x1_temperature"


SHARED_YAML = """
device:
  manufacturer: Acme
  model: Shared
holding:
  raw_value:
    address: 0
    ha:
      platform: sensor
      name: Raw
  scaled_value:
    address: 0
    multiplier: 0.1
    ha:
      platform: sensor
      name: Scaled
  low_byte:
    address: 0
    type: uint8
    ha:
      platform: sensor
      name: Low byte
  first_bit:
    address: 0
    type: bit
    ha:
      platform: sensor
      name: First bit
"""


async def test_multiple_entities_share_a_register(hass: HomeAssistant) -> None:
    directory = Path(hass.config.config_dir) / DOMAIN
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "acme_shared.yaml").write_text(SHARED_YAML, encoding="utf-8")

    entry = make_entry("acme_shared.yaml")
    client = FakeClient()
    client.values[("holding", 0)] = 215  # 0x00D7
    assert await setup_entry(hass, entry, client)

    for key, expected in [
        ("raw_value", "215"),
        ("scaled_value", "21.5"),
        ("low_byte", "215"),
        ("first_bit", "1"),
    ]:
        state = hass.states.get(eid(hass, entry, "sensor", key))
        assert state is not None
        assert state.state == expected


GROUPED_YAML = """
device:
  manufacturer: Acme
  model: Grouped
  default_groups: [basic]
holding:
  core:
    address: 0
    groups: [basic]
    ha:
      platform: sensor
      name: Core
  extra:
    address: 1
    groups: [advanced]
    ha:
      platform: sensor
      name: Extra
  hidden_only:
    address: 2
    # untagged: only in the implicit all group, shown by the all-entities switch
    ha:
      platform: sensor
      name: Hidden only
"""


async def test_group_switches_control_entity_visibility(hass: HomeAssistant) -> None:
    directory = Path(hass.config.config_dir) / DOMAIN
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "grouped.yaml").write_text(GROUPED_YAML, encoding="utf-8")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.0.2.9",
            "port": 502,
            CONF_SLAVE_ID: 3,
            CONF_FILENAME: "grouped.yaml",
        },
        unique_id="192.0.2.9:502:3",
        title="Grouped",
    )
    entry.add_to_hass(hass)
    reg = er.async_get(hass)

    with patch.object(ModbusBlockClient, "acquire", return_value=FakeClient()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # default_groups is [basic]: only 'core' is provided; the rest are absent
        # from the registry entirely (never created, not merely disabled).
        assert hass.states.get(eid(hass, entry, "sensor", "core")) is not None
        assert reg.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_extra") is None
        assert (
            reg.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_hidden_only") is None
        )

        # one config switch per named group except 'basic', which is always
        # enabled and cannot be toggled off — plus the show-all bypass switch
        assert reg.async_get_entity_id("switch", DOMAIN, f"{entry.entry_id}_group_basic") is None
        advanced = eid(hass, entry, "switch", "group_advanced")
        assert hass.states.get(advanced).state == "off"
        show_all = eid(hass, entry, "switch", "show_all_entities")
        assert hass.states.get(show_all).state == "off"

        # switch names: group names show capitalized without a joiner, and the
        # show-all switch is translated as a whole phrase matching the others
        assert hass.states.get(advanced).attributes["friendly_name"].endswith(
            "Enable Advanced entities"
        )
        # the switch icon lives in icons.json (resolved by the frontend, not
        # the state machine), keyed by the entity's translation_key
        from homeassistant.helpers.icon import async_get_icons

        icons = await async_get_icons(hass, "entity", integrations=[DOMAIN])
        assert icons[DOMAIN]["switch"]["group_enable"]["default"] == "mdi:eye-check"
        assert icons[DOMAIN]["switch"]["group_enable_all"]["default"] == "mdi:eye-check"
        assert (
            hass.states.get(show_all)
            .attributes["friendly_name"]
            .endswith("Enable all entities")
        )

        # enabling 'advanced' reloads the entry and brings 'extra' into being,
        # while an untagged entity stays hidden
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": advanced}, blocking=True
        )
        await hass.async_block_till_done()

        # the implicit basic group is not persisted in the option
        assert entry.options[OPTION_ENABLED_GROUPS] == ["advanced"]
        assert hass.states.get(eid(hass, entry, "sensor", "extra")) is not None
        assert (
            reg.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_hidden_only") is None
        )
        assert hass.states.get(eid(hass, entry, "switch", "group_advanced")).state == "on"

        # the show-all switch bypasses the group selection and reveals
        # everything, including entities tagged into no group
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": show_all}, blocking=True
        )
        await hass.async_block_till_done()

    assert entry.options[OPTION_SHOW_ALL] is True
    assert entry.options[OPTION_ENABLED_GROUPS] == ["advanced"]  # selection untouched
    assert hass.states.get(eid(hass, entry, "sensor", "hidden_only")) is not None
    assert hass.states.get(eid(hass, entry, "switch", "show_all_entities")).state == "on"


async def test_ungrouped_file_has_no_group_switches(hass: HomeAssistant) -> None:
    # without group tags everything is always shown, so there is nothing to
    # toggle — not even the all-entities switch
    write_device_file(hass)
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await setup_entry(hass, entry, FakeClient())

    group_switches = [
        e.unique_id
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if e.unique_id.startswith(f"{entry.entry_id}_group_")
    ]
    assert group_switches == []


async def test_meta_entities_live_on_configuration_device(hass: HomeAssistant) -> None:
    directory = Path(hass.config.config_dir) / DOMAIN
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "grouped.yaml").write_text(GROUPED_YAML, encoding="utf-8")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.0.2.9",
            "port": 502,
            CONF_SLAVE_ID: 3,
            CONF_FILENAME: "grouped.yaml",
        },
        unique_id="192.0.2.9:502:3",
        title="Grouped",
    )
    entry.add_to_hass(hass)
    with patch.object(ModbusBlockClient, "acquire", return_value=FakeClient()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        dev_reg = dr.async_get(hass)
        main = dev_reg.async_get_device({(DOMAIN, entry.entry_id)})
        meta = dev_reg.async_get_device({(DOMAIN, f"{entry.entry_id}_meta")})
        assert main is not None and meta is not None
        # the pair is cross-linked: both info cards show a "Connected via" jump
        assert meta.via_device_id == main.id
        assert main.via_device_id == meta.id
        assert meta.entry_type is dr.DeviceEntryType.SERVICE
        assert meta.name == "Acme Grouped Configuration"

        reg = er.async_get(hass)
        for domain_, unique in (
            ("switch", f"{entry.entry_id}_group_advanced"),
            ("sensor", f"{entry.entry_id}_reads_per_refresh"),
        ):
            entity = reg.async_get(reg.async_get_entity_id(domain_, DOMAIN, unique))
            assert entity is not None and entity.device_id == meta.id
        core = reg.async_get(reg.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_core"))
        assert core is not None and core.device_id == main.id


def test_time_mirror_sensor_has_no_state_class() -> None:
    from custom_components.modbus_connect.entity import build_mirror_description
    from custom_components.modbus_connect.models import EntityDef

    mirror = build_mirror_description(
        EntityDef(key="wake", platform="time", type="time", duplicate_as_sensor=True)
    )
    assert mirror.state_class is None  # "07:30:00" is not a measurement
    numeric = build_mirror_description(
        EntityDef(key="limit", platform="number", duplicate_as_sensor=True)
    )
    assert numeric.state_class is not None


async def test_provided_unique_ids_match_registry(hass: HomeAssistant) -> None:
    # provided_unique_ids drives the cleanup button; it must mirror exactly what
    # the platform modules register, or the button would delete live entities.
    write_device_file(hass)
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await setup_entry(hass, entry, FakeClient())

    registered = {
        e.unique_id
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    }
    assert registered == entry.runtime_data.provided_unique_ids


async def test_remove_hidden_entities_button(hass: HomeAssistant) -> None:
    directory = Path(hass.config.config_dir) / DOMAIN
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "grouped.yaml").write_text(GROUPED_YAML, encoding="utf-8")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.0.2.9",
            "port": 502,
            CONF_SLAVE_ID: 3,
            CONF_FILENAME: "grouped.yaml",
        },
        unique_id="192.0.2.9:502:3",
        title="Grouped",
    )
    entry.add_to_hass(hass)
    reg = er.async_get(hass)

    with patch.object(ModbusBlockClient, "acquire", return_value=FakeClient()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # bring 'extra' into being, then hide it again -> grayed registry row
        advanced = eid(hass, entry, "switch", "group_advanced")
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": advanced}, blocking=True
        )
        await hass.async_block_till_done()
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": advanced}, blocking=True
        )
        await hass.async_block_till_done()
        assert reg.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_extra")

        # a live entity the user disabled stays provided and must survive
        core_id = reg.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_core")
        reg.async_update_entity(core_id, disabled_by=er.RegistryEntryDisabler.USER)

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": eid(hass, entry, "button", "remove_hidden_entities")},
            blocking=True,
        )
        await hass.async_block_till_done()

    # the hidden leftover is gone ...
    assert reg.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_extra") is None
    # ... but the provided-though-disabled entity kept its row and customization
    core = reg.async_get(core_id)
    assert core is not None
    assert core.disabled_by is er.RegistryEntryDisabler.USER
    # the meta entities themselves survive too
    assert reg.async_get_entity_id("switch", DOMAIN, f"{entry.entry_id}_group_advanced")
    assert reg.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_reads_per_refresh")
