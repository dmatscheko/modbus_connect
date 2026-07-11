"""Golden tests: old-format YAML through the converter and the new schema."""

import importlib.util
import io
from pathlib import Path

import pytest
import yaml

from custom_components.modbus_connect.schema import parse_device

# The converter is a standalone script with a hyphenated filename (named after the source
# format it converts), so it is loaded by path rather than imported as a module.
_convert_path = (
    Path(__file__).resolve().parent.parent
    / "support" / "converter" / "modbus_local_gateway" / "modbus_local_gateway-convert.py"
)
_spec = importlib.util.spec_from_file_location("mlg_convert", _convert_path)
_mlg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mlg)
SECTION_COMMENTS = _mlg.SECTION_COMMENTS
convert_device = _mlg.convert_device
dump_device_yaml = _mlg.dump_device_yaml

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


# --- regressions: outputs that used to fail schema validation ----------------


def _mini(section: str, **entities) -> dict:
    return {"device": {"manufacturer": "Acme", "model": "X1"}, section: entities}


def test_select_without_options_is_skipped():
    doc = convert_device(
        _mini(
            "read_write_word",
            bad={"address": 1, "control": "select"},
            ok={"address": 2},
        ),
        "old.yaml",
    )
    assert "bad" not in doc.get("holding", {})
    assert "ok" in doc["holding"]
    parse_device(doc, "old.yaml")  # and the rest still validates


def test_unit_and_precision_dropped_for_control_platforms():
    # old files legally carried unit/precision on any control; HA selects have
    # neither, and emitting them made a file the integration refused to load
    doc = convert_device(
        _mini(
            "read_write_word",
            mode={
                "address": 1,
                "control": "select",
                "options": {0: "Off", 1: "On"},
                "unit_of_measurement": "Celsius",
                "precision": 1,
            },
        ),
        "old.yaml",
    )
    dev = parse_device(doc, "old.yaml")
    ha = dev.entities[0].ha
    assert "native_unit_of_measurement" not in ha
    assert "suggested_display_precision" not in ha


def test_non_integer_flag_bits_dropped():
    doc = convert_device(
        _mini("read_only_word", f={"address": 1, "flags": {"x": "Bad", 2: "Good"}}),
        "old.yaml",
    )
    dev = parse_device(doc, "old.yaml")
    assert dev.entities[0].flags == {1: "Good"}  # 1-indexed 2 -> 0-indexed 1


def test_duplicate_key_rename_is_collision_checked():
    old = {
        "device": {"manufacturer": "Acme", "model": "X1"},
        "read_write_word": {"x": {"address": 1}, "x_input": {"address": 2}},
        "read_only_word": {"x": {"address": 3}},
    }
    doc = convert_device(old, "old.yaml")
    keys = set(doc["holding"]) | set(doc["input"])
    assert len(keys) == 3  # nothing silently overwritten
    parse_device(doc, "old.yaml")


def test_number_step_defaults_to_multiplier():
    # the old integration uses the multiplier as the step when none is given
    doc = convert_device(
        _mini(
            "read_write_word",
            t={"address": 1, "multiplier": 0.1, "control": "number",
               "number": {"min": 5, "max": 30}},
            flow={"address": 2, "multiplier": 10, "control": "number",
                  "number": {"min": 0, "max": 500}},
            plain={"address": 3, "control": "number", "number": {"min": 0, "max": 9}},
        ),
        "old.yaml",
    )
    assert doc["holding"]["t"]["ha"]["step"] == pytest.approx(0.1)
    assert doc["holding"]["flow"]["ha"]["step"] == 10
    assert "step" not in doc["holding"]["plain"]["ha"]  # multiplier 1 keeps HA's default
    parse_device(doc, "old.yaml")


def test_number_without_min_max_is_skipped():
    # the old integration never creates these; our schema would reject them
    doc = convert_device(
        _mini("read_write_word", bad={"address": 1, "control": "number"}),
        "old.yaml",
    )
    assert "bad" not in doc.get("holding", {})


def test_word_binary_sensor_reads_on_as_one():
    # old semantics: is_on = (value == on), on defaults to True == 1 on word
    # registers, and 'off' is never consulted — anything != on reads as off
    doc = convert_device(
        _mini(
            "read_only_word",
            plain={"address": 1, "control": "binary_sensor"},
            explicit={"address": 2, "control": "binary_sensor", "on": 2, "off": 1},
        ),
        "old.yaml",
    )
    assert doc["input"]["plain"]["on_value"] == 1
    assert doc["input"]["explicit"]["on_value"] == 2
    assert "off_value" not in doc["input"]["explicit"]
    dev = parse_device(doc, "old.yaml")
    assert entity(dev, "plain").on_value == 1


def test_word_switch_defaults_on_to_one():
    doc = convert_device(
        _mini("read_write_word", s={"address": 1, "control": "switch"}),
        "old.yaml",
    )
    assert doc["holding"]["s"]["on_value"] == 1
    parse_device(doc, "old.yaml")


def test_disallowed_control_for_section_is_skipped():
    # the old integration refuses writable controls on read-only tables
    doc = convert_device(
        _mini(
            "read_only_word",
            bad={"address": 1, "control": "number", "number": {"min": 0, "max": 9}},
            ok={"address": 2},
        ),
        "old.yaml",
    )
    assert "bad" not in doc.get("input", {})
    assert "ok" in doc["input"]


def test_text_without_string_is_skipped():
    # the old integration created these but raised on every write
    doc = convert_device(
        _mini("read_write_word", bad={"address": 1, "control": "text"}),
        "old.yaml",
    )
    assert "bad" not in doc.get("holding", {})


def test_multiplier_folds_into_map_keys():
    # the old pipeline scales the value BEFORE the map lookup (and selects write
    # the mapped key back through the same scaling); ours maps raw values
    doc = convert_device(
        _mini(
            "read_write_word",
            mode={"address": 1, "multiplier": 0.5, "control": "select",
                  "options": {1: "Low", 2: "High"}},
            odd={"address": 2, "multiplier": 0.4, "map": {1: "X"}},
            flagged={"address": 3, "multiplier": 0.5, "flags": {1: "A"}},
        ),
        "old.yaml",
    )
    assert doc["holding"]["mode"]["map"] == {2: "Low", 4: "High"}
    assert "multiplier" not in doc["holding"]["mode"]
    assert "odd" not in doc["holding"]  # 1/0.4 = 2.5: no raw value maps to it
    assert "flagged" not in doc["holding"]  # scaled bit positions: not representable
    parse_device(doc, "old.yaml")
