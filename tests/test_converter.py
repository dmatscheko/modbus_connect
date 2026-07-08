"""Golden tests: old-format YAML through the converter and the new schema."""

import io

import pytest
import yaml

from converter.convert import SECTION_COMMENTS, convert_device, dump_device_yaml
from custom_components.modbus_connect.schema import parse_device

OLD = {
    "device": {"manufacturer": "Acme", "model": "X1", "max_register_read": 32},
    "read_write_word": {
        "temp": {
            "address": 1,
            "multiplier": 0.1,
            "offset": -40,
            "unit_of_measurement": "Celsius",
            "precision": 1,
        },
        "mode": {"address": 2, "control": "select", "options": {0: "Off", 1: "On"}},
        "setpoint": {
            "address": 3,
            "control": "number",
            "number": {"min": 5, "max": 30, "step": 0.5, "mode": "slider"},
            "unit_of_measurement": "Celsius",
        },
        "status_flags": {"address": 4, "flags": {1: "A", 3: "B"}},
        "masked": {"address": 5, "bits": 4, "shift_bits": 4},
        "big": {"address": 6, "size": 2, "signed": True, "swap": "word"},
        "energy": {"address": 8, "sum_scale": [1, 10000], "unit_of_measurement": "kWh"},
        "label": {"address": 10, "size": 4, "string": True, "control": "text"},
        "power_switch": {"address": 14, "control": "switch", "switch": {"on": 2, "off": 0}},
    },
    "read_only_word": {
        "voltage": {"address": 20, "float": True, "size": 2, "unit_of_measurement": "Volts"},
        "custom_unit": {"address": 22, "unit_of_measurement": "kVArh"},
    },
    "read_write_boolean": {"relay": {"address": 0, "control": "switch"}},
    "read_only_boolean": {"door": {"address": 1}},
}


def convert_and_parse():
    return parse_device(convert_device(OLD, "old.yaml"), "old.yaml")


def entity(dev, key):
    return next(e for e in dev.entities if e.key == key)


def test_all_entities_survive():
    dev = convert_and_parse()
    assert len(dev.entities) == 13
    assert dev.manufacturer == "Acme"
    assert dev.max_read == 32


def test_sensor_with_uom_preset():
    e = entity(convert_and_parse(), "temp")
    assert e.table == "holding"
    assert e.multiplier == pytest.approx(0.1)
    assert e.offset == -40
    assert e.ha["native_unit_of_measurement"] == "°C"
    assert str(e.ha["device_class"]) == "temperature"
    assert str(e.ha["state_class"]) == "measurement"
    assert e.ha["suggested_display_precision"] == 1


def test_select_options_become_map():
    e = entity(convert_and_parse(), "mode")
    assert e.platform == "select"
    assert e.value_map == {0: "Off", 1: "On"}


def test_number_limits_move_to_ha():
    e = entity(convert_and_parse(), "setpoint")
    assert e.platform == "number"
    assert e.ha["native_min_value"] == 5
    assert e.ha["native_max_value"] == 30
    assert e.ha["native_step"] == pytest.approx(0.5)
    assert str(e.ha["mode"]) == "slider"
    # numbers are not sensors: no state_class
    assert "state_class" not in e.ha


def test_flags_reindexed_to_zero_based():
    e = entity(convert_and_parse(), "status_flags")
    assert e.flags == {0: "A", 2: "B"}


def test_bits_shift_become_mask():
    e = entity(convert_and_parse(), "masked")
    assert e.mask == 0x00F0


def test_size_signed_become_type():
    e = entity(convert_and_parse(), "big")
    assert e.type == "int32"
    assert e.swap == "word"
    assert e.count == 2


def test_sum_scale_passthrough():
    e = entity(convert_and_parse(), "energy")
    assert e.sum_scale == (1, 10000)
    assert str(e.ha["state_class"]) == "total_increasing"


def test_string_text_entity():
    e = entity(convert_and_parse(), "label")
    assert e.platform == "text"
    assert e.type == "string"
    assert e.count == 4


def test_switch_on_off_values():
    e = entity(convert_and_parse(), "power_switch")
    assert e.on_value == 2
    assert e.off_value == 0


def test_input_register_float():
    e = entity(convert_and_parse(), "voltage")
    assert e.table == "input"
    assert e.type == "float32"


def test_preset_without_device_class_gets_no_state_class():
    # old get_uom(): state_class was dropped when no device_class resolved
    e = entity(convert_and_parse(), "custom_unit")
    assert e.ha["native_unit_of_measurement"] == "kVArh"
    assert "state_class" not in e.ha
    assert "device_class" not in e.ha


def test_bit_tables():
    dev = convert_and_parse()
    relay = entity(dev, "relay")
    assert relay.table == "coil"
    assert relay.platform == "switch"
    door = entity(dev, "door")
    assert door.table == "discrete"
    assert door.platform == "binary_sensor"


def dump_old():
    doc = convert_device(OLD, "old.yaml")
    buf = io.StringIO()
    dump_device_yaml(buf, doc)
    return doc, buf.getvalue()


def test_each_section_is_prefixed_with_its_comment():
    doc, text = dump_old()
    lines = text.splitlines()
    # OLD exercises every table, so every documented section should appear
    for section in ("device", "holding", "input", "coil", "discrete"):
        assert section in doc
        i = lines.index(f"{section}:")
        assert lines[i - 1] == f"# {SECTION_COMMENTS[section]}"


def test_dump_round_trips_and_keeps_hex_mask():
    doc, text = dump_old()
    # comments are ignored on load: the data round-trips unchanged
    assert yaml.safe_load(text) == doc
    # masks stay hex-formatted for humans (0x00F0 from bits/shift_bits)
    assert "mask: 0xF0" in text
