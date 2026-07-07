"""Tests for YAML schema validation."""

import pytest

from custom_components.modbus_connect.schema import DeviceSchemaError, parse_device

DEVICE = {"device": {"manufacturer": "Acme", "model": "X1"}}


def doc(section: str = "holding", **entities) -> dict:
    return {**DEVICE, section: entities}


def test_minimal_sensor():
    dev = parse_device(doc(temp={"address": 7, "ha": {"platform": "sensor"}}), "t.yaml")
    (e,) = dev.entities
    assert e.key == "temp"
    assert e.table == "holding"
    assert e.type == "uint16"
    assert e.count == 1


def test_section_sets_table():
    dev = parse_device(doc("input", v={"address": 3, "ha": {"platform": "sensor"}}), "t.yaml")
    assert dev.entities[0].table == "input"


def test_sensor_allowed_on_writable_table():
    # a holding register can be exposed read-only on purpose
    dev = parse_device(doc(x={"address": 1, "ha": {"platform": "sensor"}}), "t.yaml")
    assert dev.entities[0].table == "holding"
    assert not dev.entities[0].writes


def test_table_key_rejected():
    with pytest.raises(DeviceSchemaError, match="grouped by the"):
        parse_device(
            doc(x={"address": 1, "table": "input", "ha": {"platform": "sensor"}}), "t.yaml"
        )


def test_duplicate_key_across_sections():
    data = {
        **DEVICE,
        "holding": {"x": {"address": 1, "ha": {"platform": "sensor"}}},
        "input": {"x": {"address": 2, "ha": {"platform": "sensor"}}},
    }
    with pytest.raises(DeviceSchemaError, match="unique across sections"):
        parse_device(data, "t.yaml")


def test_no_entities_rejected():
    with pytest.raises(DeviceSchemaError, match="no entities"):
        parse_device(dict(DEVICE), "t.yaml")


def test_old_format_detected():
    with pytest.raises(DeviceSchemaError, match="convert"):
        parse_device({"device": {}, "read_write_word": {}}, "t.yaml")


def test_unknown_modbus_key_names_entity():
    with pytest.raises(DeviceSchemaError, match=r"entity 'x'.*multiplyer"):
        parse_device(doc(x={"address": 1, "multiplyer": 2, "ha": {"platform": "sensor"}}), "t.yaml")


def test_unknown_ha_field_rejected():
    with pytest.raises(DeviceSchemaError, match=r"ha\.icom"):
        parse_device(doc(x={"address": 1, "ha": {"platform": "sensor", "icom": "mdi:x"}}), "t.yaml")


def test_ha_aliases_resolved():
    dev = parse_device(
        doc(x={"address": 1, "ha": {
            "platform": "sensor",
            "unit_of_measurement": "W",
            "precision": 1,
            "enabled_by_default": False,
        }}),
        "t.yaml",
    )
    ha = dev.entities[0].ha
    assert ha["native_unit_of_measurement"] == "W"
    assert ha["suggested_display_precision"] == 1
    assert ha["entity_registry_enabled_default"] is False


def test_invalid_device_class_lists_alternatives():
    with pytest.raises(DeviceSchemaError, match="carbon_dioxide"):
        parse_device(
            doc(x={"address": 1, "ha": {"platform": "sensor", "device_class": "co2"}}),
            "t.yaml",
        )


def test_sum_scale_sets_count():
    dev = parse_device(
        doc(x={"address": 1, "sum_scale": [1, 10000, 100000000], "ha": {"platform": "sensor"}}),
        "t.yaml",
    )
    assert dev.entities[0].count == 3


def test_count_conflict_rejected():
    with pytest.raises(DeviceSchemaError, match="contradicts"):
        parse_device(
            doc(x={"address": 1, "type": "uint32", "count": 3, "ha": {"platform": "sensor"}}),
            "t.yaml",
        )


def test_string_requires_count():
    with pytest.raises(DeviceSchemaError, match="count"):
        parse_device(doc(x={"address": 1, "type": "string", "ha": {"platform": "sensor"}}), "t.yaml")


def test_float_with_map_allowed():
    dev = parse_device(
        doc(x={"address": 1, "type": "float32", "map": {0: "A"}, "ha": {"platform": "sensor"}}),
        "t.yaml",
    )
    assert dev.entities[0].value_map == {0: "A"}


def test_flags_bit_out_of_range():
    with pytest.raises(DeviceSchemaError, match="0-indexed"):
        parse_device(doc(x={"address": 1, "flags": {16: "A"}, "ha": {"platform": "sensor"}}), "t.yaml")


def test_bit_table_rejects_numeric_options():
    with pytest.raises(DeviceSchemaError, match="not valid for a coil"):
        parse_device(
            doc("coil", x={"address": 1, "multiplier": 2, "ha": {"platform": "switch"}}),
            "t.yaml",
        )


def test_writing_platform_needs_writable_table():
    with pytest.raises(DeviceSchemaError, match="read-only"):
        parse_device(
            doc("input", x={"address": 1, "ha": {"platform": "number", "min": 0, "max": 5}}),
            "t.yaml",
        )


def test_button_requires_write_value():
    with pytest.raises(DeviceSchemaError, match="write_value"):
        parse_device(doc(x={"address": 1, "ha": {"platform": "button"}}), "t.yaml")


def test_select_requires_map():
    with pytest.raises(DeviceSchemaError, match="map"):
        parse_device(doc(x={"address": 1, "ha": {"platform": "select"}}), "t.yaml")


def test_number_requires_min_max():
    with pytest.raises(DeviceSchemaError, match=r"ha\.min"):
        parse_device(doc(x={"address": 1, "ha": {"platform": "number"}}), "t.yaml")


def test_read_modify_write_needs_mask():
    with pytest.raises(DeviceSchemaError, match="mask"):
        parse_device(
            doc(x={"address": 1, "read_modify_write": True,
                   "ha": {"platform": "number", "min": 0, "max": 5}}),
            "t.yaml",
        )


def test_duplicate_as_sensor_only_for_writers():
    with pytest.raises(DeviceSchemaError, match="duplicate_as_sensor"):
        parse_device(
            doc(x={"address": 1, "duplicate_as_sensor": True, "ha": {"platform": "sensor"}}),
            "t.yaml",
        )


def test_device_section_required():
    with pytest.raises(DeviceSchemaError, match="device"):
        parse_device({"holding": {"x": {"address": 1, "ha": {"platform": "sensor"}}}}, "t.yaml")


# --- internal entities ------------------------------------------------------------


def test_internal_entity():
    dev = parse_device(doc(x={"address": 1, "internal": True, "multiplier": 0.1}), "t.yaml")
    (e,) = dev.entities
    assert e.internal
    assert e.platform == "internal"
    assert not e.writes
    assert e.ha == {}


def test_internal_rejects_ha_block():
    with pytest.raises(DeviceSchemaError, match="internal"):
        parse_device(
            doc(x={"address": 1, "internal": True, "ha": {"platform": "sensor"}}), "t.yaml"
        )


def test_internal_rejects_platform_specific_keys():
    with pytest.raises(DeviceSchemaError, match="write_value"):
        parse_device(doc(x={"address": 1, "internal": True, "write_value": 1}), "t.yaml")


def test_template_can_target_internal_entity():
    data = {
        **DEVICE,
        "holding": {
            "target": {"address": 1, "internal": True},
            "temp": {"address": 0, "ha": {"platform": "sensor"}},
        },
        "template": {
            "c": {
                "ha": {"platform": "climate"},
                "current_temperature": "{{ temp }}",
                "set_temperature": {"entity": "target"},
            },
        },
    }
    dev = parse_device(data, "t.yaml")
    assert dev.templates[0].config["set_temperature"].entity == "target"


# --- template: section -----------------------------------------------------------


def tdoc(**templates) -> dict:
    return {
        **DEVICE,
        "holding": {
            "temp": {"address": 1, "multiplier": 0.1, "ha": {"platform": "sensor"}},
            "setpoint": {"address": 2, "ha": {"platform": "number", "min": 0, "max": 60}},
            "mode": {"address": 3, "map": {0: "Off", 1: "Auto"}, "ha": {"platform": "select"}},
        },
        "input": {"power": {"address": 10, "ha": {"platform": "sensor"}}},
        "template": templates,
    }


def test_template_sensor():
    dev = parse_device(
        tdoc(cop={"state": "{{ power / 1000 }}", "ha": {"platform": "sensor", "precision": 2}}),
        "t.yaml",
    )
    (t,) = dev.templates
    assert t.platform == "sensor"
    assert t.config["state"] == "{{ power / 1000 }}"
    assert t.ha["suggested_display_precision"] == 2


def test_template_requires_state():
    with pytest.raises(DeviceSchemaError, match="state"):
        parse_device(tdoc(x={"ha": {"platform": "sensor"}}), "t.yaml")


def test_template_key_collision():
    with pytest.raises(DeviceSchemaError, match="collides"):
        parse_device(tdoc(temp={"state": "{{ 1 }}", "ha": {"platform": "sensor"}}), "t.yaml")


def test_template_platform_restricted():
    with pytest.raises(DeviceSchemaError, match="template platform"):
        parse_device(tdoc(x={"state": "{{ 1 }}", "ha": {"platform": "button"}}), "t.yaml")


def test_climate_template_full():
    dev = parse_device(
        tdoc(hot_water={
            "ha": {"platform": "climate", "name": "Hot water"},
            "current_temperature": "{{ temp }}",
            "target_temperature": "{{ setpoint }}",
            "hvac_mode": "{{ 'heat' if mode == 'Auto' else 'off' }}",
            "min_temp": 30,
            "max_temp": 60,
            "temp_step": 0.5,
            "set_temperature": {"entity": "setpoint"},
            "set_hvac_mode": {"entity": "mode", "map": {"heat": "Auto", "off": "Off"}},
        }),
        "t.yaml",
    )
    (t,) = dev.templates
    assert t.platform == "climate"
    assert t.config["set_temperature"].entity == "setpoint"
    assert t.config["set_hvac_mode"].value_map == {"heat": "Auto", "off": "Off"}
    assert t.config["hvac_modes"] == ["heat", "off"]  # derived from the map


def test_climate_action_must_target_writable_table():
    with pytest.raises(DeviceSchemaError, match="read-only"):
        parse_device(
            tdoc(c={
                "ha": {"platform": "climate"},
                "set_temperature": {"entity": "power"},  # input table
            }),
            "t.yaml",
        )


def test_climate_action_unknown_entity():
    with pytest.raises(DeviceSchemaError, match="unknown entity"):
        parse_device(
            tdoc(c={"ha": {"platform": "climate"}, "set_temperature": {"entity": "nope"}}),
            "t.yaml",
        )


def test_climate_invalid_hvac_mode():
    with pytest.raises(DeviceSchemaError, match="hvac_modes"):
        parse_device(
            tdoc(c={"ha": {"platform": "climate"}, "hvac_modes": ["warp_drive"]}),
            "t.yaml",
        )


def test_switch_template_requires_both_actions():
    with pytest.raises(DeviceSchemaError, match="turn_off"):
        parse_device(
            tdoc(s={
                "ha": {"platform": "switch"},
                "state": "{{ temp > 0 }}",
                "turn_on": {"entity": "setpoint", "value": 1},
            }),
            "t.yaml",
        )


def test_fixed_action_requires_value():
    with pytest.raises(DeviceSchemaError, match="needs a 'value'"):
        parse_device(
            tdoc(s={
                "ha": {"platform": "switch"},
                "state": "{{ temp > 0 }}",
                "turn_on": {"entity": "setpoint"},
                "turn_off": {"entity": "setpoint", "value": 0},
            }),
            "t.yaml",
        )


def test_value_action_rejects_map():
    with pytest.raises(DeviceSchemaError, match="unknown keys"):
        parse_device(
            tdoc(n={
                "ha": {"platform": "number", "min": 0, "max": 100},
                "state": "{{ temp }}",
                "set_value": {"entity": "setpoint", "map": {"a": 1}},
            }),
            "t.yaml",
        )


def test_select_template_options_from_target_map():
    dev = parse_device(
        tdoc(s={
            "ha": {"platform": "select"},
            "state": "{{ mode }}",
            "select_option": {"entity": "mode"},
        }),
        "t.yaml",
    )
    assert dev.templates[0].config["options"] == ["Off", "Auto"]


def test_select_template_without_option_source():
    with pytest.raises(DeviceSchemaError, match="options"):
        parse_device(
            tdoc(s={
                "ha": {"platform": "select"},
                "state": "{{ setpoint }}",
                "select_option": {"entity": "setpoint"},  # no map anywhere
            }),
            "t.yaml",
        )


def test_cover_template_needs_state_or_position():
    with pytest.raises(DeviceSchemaError, match="is_closed"):
        parse_device(
            tdoc(c={
                "ha": {"platform": "cover"},
                "open_cover": {"entity": "setpoint", "value": 1},
            }),
            "t.yaml",
        )


def test_fan_preset_needs_modes():
    with pytest.raises(DeviceSchemaError, match="preset_modes"):
        parse_device(
            tdoc(f={
                "ha": {"platform": "fan"},
                "state": "{{ temp > 0 }}",
                "preset_mode": "{{ mode }}",
                "turn_on": {"entity": "setpoint", "value": 1},
                "turn_off": {"entity": "setpoint", "value": 0},
            }),
            "t.yaml",
        )


def test_template_number_requires_min_max():
    with pytest.raises(DeviceSchemaError, match=r"ha\.min"):
        parse_device(
            tdoc(n={
                "ha": {"platform": "number"},
                "state": "{{ temp }}",
                "set_value": {"entity": "setpoint"},
            }),
            "t.yaml",
        )


def test_unknown_template_key_lists_valid():
    with pytest.raises(DeviceSchemaError, match="set_percentage"):
        parse_device(
            tdoc(f={
                "ha": {"platform": "fan"},
                "state": "{{ temp > 0 }}",
                "set_speed": {"entity": "setpoint"},
                "turn_on": {"entity": "setpoint", "value": 1},
                "turn_off": {"entity": "setpoint", "value": 0},
            }),
            "t.yaml",
        )
