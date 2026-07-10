"""Tests for YAML schema validation."""

import pytest

from custom_components.modbus_connect.models import SwitchTarget
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


@pytest.mark.parametrize(
    ("typ", "weights", "count"),
    [
        ("uint16", 3, 3),
        ("uint8", 3, 2),  # 1.5 registers -> read 2
        ("uint8", 6, 3),
        ("int8", 2, 1),
        ("bit", 20, 2),
        ("int1", 4, 1),
        ("uint32", 2, 4),
        ("float32", 2, 4),
    ],
)
def test_sum_scale_count_follows_type(typ, weights, count):
    dev = parse_device(
        doc(x={"address": 1, "type": typ, "sum_scale": [1] * weights,
               "ha": {"platform": "sensor"}}),
        "t.yaml",
    )
    assert dev.entities[0].count == count


@pytest.mark.parametrize("typ", ["bit", "int1", "uint8", "int8", "float16"])
def test_small_types_read_one_register(typ):
    dev = parse_device(
        doc(x={"address": 1, "type": typ, "ha": {"platform": "sensor"}}), "t.yaml"
    )
    assert dev.entities[0].count == 1
    assert dev.entities[0].type == ("bit" if typ == "int1" else typ)


def test_device_defaults_parsed():
    data = {
        "device": {
            "manufacturer": "Acme",
            "model": "X1",
            "modbus_id": 247,
            "prefix": "acme_x1",
            "scan_interval": 15,
        },
        "holding": {"x": {"address": 1, "ha": {"platform": "sensor"}}},
    }
    dev = parse_device(data, "t.yaml")
    assert dev.modbus_id == 247
    assert dev.prefix == "acme_x1"
    assert dev.scan_interval == 15


def test_interval_and_planning_hints_parsed():
    data = {
        "device": {
            "manufacturer": "Acme",
            "model": "X1",
            "min_scan_interval": 10,
            "scan_interval": 30,
            "bad_addresses": {"holding": [0x99], "input": [5]},
            "split_before": {"holding": [0x30, 400]},
        },
        "holding": {"x": {"address": 1, "scan_interval": 60,
                          "ha": {"platform": "sensor"}}},
    }
    dev = parse_device(data, "t.yaml")
    assert dev.min_scan_interval == 10
    assert dev.scan_interval == 30
    assert dev.bad_addresses == frozenset({("holding", 0x99), ("input", 5)})
    assert dev.boundaries == frozenset({("holding", 0x30), ("holding", 400)})
    assert dev.entities[0].scan_interval == 60


def test_connection_tuning_parsed():
    data = {
        "device": {
            "manufacturer": "Acme",
            "model": "X1",
            "timeout": 5,
            "retries": 3,
            "request_delay": 0.05,
        },
        "holding": {"x": {"address": 1, "ha": {"platform": "sensor"}}},
    }
    dev = parse_device(data, "t.yaml")
    assert dev.timeout == 5
    assert dev.retries == 3
    assert dev.request_delay == pytest.approx(0.05)


def test_connection_tuning_defaults_absent():
    dev = parse_device(doc(x={"address": 1, "ha": {"platform": "sensor"}}), "t.yaml")
    assert dev.timeout is None
    assert dev.retries is None
    assert dev.request_delay is None


@pytest.mark.parametrize(
    ("field", "match"),
    [
        ({"timeout": 0}, "device.timeout"),
        ({"timeout": 61}, "device.timeout"),
        ({"timeout": "fast"}, "device.timeout"),
        ({"retries": 11}, "device.retries"),
        ({"request_delay": -0.1}, "device.request_delay"),
        ({"request_delay": 6}, "device.request_delay"),
    ],
)
def test_connection_tuning_invalid(field, match):
    data = {
        "device": {"manufacturer": "Acme", "model": "X1", **field},
        "holding": {"x": {"address": 1, "ha": {"platform": "sensor"}}},
    }
    with pytest.raises(DeviceSchemaError, match=match):
        parse_device(data, "t.yaml")


@pytest.mark.parametrize(
    ("hints", "match"),
    [
        ({"bad_addresses": {"nosuch": [1]}}, "unknown table"),
        ({"bad_addresses": {"holding": []}}, "non-empty list"),
        ({"bad_addresses": [1, 2]}, "mapping of table"),
        ({"split_before": {"holding": [70000]}}, "between 0 and 65535"),
    ],
)
def test_planning_hints_invalid(hints, match):
    data = {
        "device": {"manufacturer": "Acme", "model": "X1", **hints},
        "holding": {"x": {"address": 1, "ha": {"platform": "sensor"}}},
    }
    with pytest.raises(DeviceSchemaError, match=match):
        parse_device(data, "t.yaml")


def test_button_single_template_write_value_parsed():
    dev = parse_device(
        doc(b={"address": 0, "write_value": "{{ now().hour }}",
               "ha": {"platform": "button"}}),
        "t.yaml",
    )
    assert dev.entities[0].write_value == "{{ now().hour }}"


def test_button_blank_template_write_value_rejected():
    with pytest.raises(DeviceSchemaError, match="must not be empty"):
        parse_device(
            doc(b={"address": 0, "write_value": "  ", "ha": {"platform": "button"}}),
            "t.yaml",
        )


def test_button_list_write_value_parsed():
    dev = parse_device(
        doc(sync={"address": 0, "write_value": [1, "{{ now().hour }}"],
                  "ha": {"platform": "button", "name": "S"}}),
        "t.yaml",
    )
    (e,) = dev.entities
    assert e.write_value == (1, "{{ now().hour }}")  # stored as an immutable tuple


@pytest.mark.parametrize(
    ("write_value", "match"),
    [
        ([], "must not be empty"),
        ([1, True], "numbers or template strings"),
        ([1, "  "], "must not be empty"),  # blank template string
    ],
)
def test_button_list_write_value_invalid(write_value, match):
    with pytest.raises(DeviceSchemaError, match=match):
        parse_device(
            doc(sync={"address": 0, "write_value": write_value,
                      "ha": {"platform": "button"}}),
            "t.yaml",
        )


def test_list_write_value_on_non_button_rejected():
    with pytest.raises(DeviceSchemaError, match="only valid for buttons"):
        parse_device(
            doc(x={"address": 0, "write_value": [1, 2], "ha": {"platform": "sensor"}}),
            "t.yaml",
        )


def test_list_write_value_on_coil_rejected():
    data = {
        "device": {"manufacturer": "A", "model": "X"},
        "coil": {"b": {"address": 0, "write_value": [1, 2],
                       "ha": {"platform": "button"}}},
    }
    with pytest.raises(DeviceSchemaError, match="can't target a coil"):
        parse_device(data, "t.yaml")


def test_device_defaults_absent():
    dev = parse_device(doc(x={"address": 1, "ha": {"platform": "sensor"}}), "t.yaml")
    assert dev.modbus_id is None
    assert dev.prefix is None
    assert dev.sw_version is None
    assert dev.hw_version is None
    assert dev.serial_number is None


def test_device_info_fields_parsed():
    data = {
        "device": {
            "manufacturer": "Acme", "model": "X1",
            "sw_version": "FW {{ fw }}", "hw_version": "Gen4", "serial_number": "{{ sn }}",
        },
        "holding": {"x": {"address": 1, "ha": {"platform": "sensor"}}},
    }
    dev = parse_device(data, "t.yaml")
    assert dev.sw_version == "FW {{ fw }}"
    assert dev.hw_version == "Gen4"
    assert dev.serial_number == "{{ sn }}"


def test_device_info_field_must_be_string():
    with pytest.raises(DeviceSchemaError, match="sw_version"):
        parse_device(
            {"device": {"manufacturer": "Acme", "model": "X1", "sw_version": 159},
             "holding": {"x": {"address": 1, "ha": {"platform": "sensor"}}}},
            "t.yaml",
        )


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


def test_read_register_parsed():
    dev = parse_device(
        doc(x={"address": 36, "read_register": "{{ y }}",
               "ha": {"platform": "number", "min": 0, "max": 50}}),
        "t.yaml",
    )
    assert dev.entities[0].read_register == "{{ y }}"


def test_read_register_rejected_on_read_only_platform():
    with pytest.raises(DeviceSchemaError, match="read_register"):
        parse_device(
            doc(x={"address": 1, "read_register": "{{ y }}", "ha": {"platform": "sensor"}}),
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


# --- error branches, exhaustively -------------------------------------------------

VALID_SENSOR = {"address": 0, "ha": {"platform": "sensor"}}

ERROR_CASES = [
    ("not_mapping", [], "YAML mapping"),
    ("unknown_top_level", {**DEVICE, "holdings": {}}, "unknown top-level keys"),
    ("device_missing", {"holding": {"x": VALID_SENSOR}}, "missing 'device:'"),
    ("manufacturer_missing", {"device": {"model": "X"}}, "device.manufacturer"),
    (
        "unknown_device_key",
        {"device": {"manufacturer": "A", "model": "X", "foo": 1}},
        "unknown device keys",
    ),
    (
        "bad_device_scan_interval",
        {"device": {"manufacturer": "A", "model": "X", "scan_interval": 0}},
        "device.scan_interval",
    ),
    (
        "bad_max_register_read",
        {"device": {"manufacturer": "A", "model": "X", "max_register_read": 0}},
        "device.max_register_read",
    ),
    (
        "bad_device_modbus_id",
        {"device": {"manufacturer": "A", "model": "X", "modbus_id": 256}},
        "device.modbus_id",
    ),
    (
        "bad_device_prefix",
        {"device": {"manufacturer": "A", "model": "X", "prefix": ""}},
        "device.prefix",
    ),
    ("section_not_mapping", {**DEVICE, "holding": []}, "must be a mapping of entity"),
    (
        "template_not_mapping",
        {**DEVICE, "holding": {"x": VALID_SENSOR}, "template": [1]},
        "'template:' must be a mapping",
    ),
    (
        "template_collides",
        {
            **DEVICE,
            "holding": {"x": VALID_SENSOR},
            "template": {"x": {"state": "{{ 1 }}", "ha": {"platform": "sensor"}}},
        },
        "collides with an entity",
    ),
    ("entity_not_mapping", doc(x=5), "entity must be a mapping"),
    (
        "internal_with_ha",
        doc(x={"address": 0, "internal": True, "ha": {"platform": "sensor"}}),
        "must not have an 'ha:' block",
    ),
    (
        "internal_with_on",
        doc(x={"address": 0, "internal": True, "on_value": 1}),
        "not valid for internal",
    ),
    (
        "internal_with_mirror",
        doc(x={"address": 0, "internal": True, "duplicate_as_sensor": True}),
        "not valid for internal",
    ),
    ("internal_not_bool", doc(x={"address": 0, "internal": "yes"}), "true or false"),
    ("address_missing", doc(x={"ha": {"platform": "sensor"}}), "'address' is required"),
    (
        "address_out_of_range",
        doc(x={"address": 70000, "ha": {"platform": "sensor"}}),
        "address must be an integer",
    ),
    (
        "sum_scale_not_list",
        doc(x={"address": 0, "sum_scale": 5, "ha": {"platform": "sensor"}}),
        "sum_scale must be a non-empty list",
    ),
    (
        "bit_table_with_type",
        doc("coil", x={"address": 0, "type": "uint16", "ha": {"platform": "switch"}}),
        "not valid for a coil",
    ),
    (
        "bit_table_with_multiplier",
        doc("coil", x={"address": 0, "multiplier": 2, "ha": {"platform": "switch"}}),
        "'multiplier' is not valid for a coil",
    ),
    (
        "unknown_type",
        doc(x={"address": 0, "type": "uint24", "ha": {"platform": "sensor"}}),
        "unknown type",
    ),
    (
        "type_not_a_string",
        doc(x={"address": 0, "type": 16, "ha": {"platform": "sensor"}}),
        "unknown type",
    ),
    (
        "unknown_swap",
        doc(x={"address": 0, "swap": "nibble", "ha": {"platform": "sensor"}}),
        "unknown swap",
    ),
    (
        "mask_on_float",
        doc(x={"address": 0, "type": "float32", "mask": 1, "ha": {"platform": "sensor"}}),
        "'mask' requires an integer type",
    ),
    (
        "multiplier_zero",
        doc(x={"address": 0, "multiplier": 0, "ha": {"platform": "sensor"}}),
        "multiplier must not be 0",
    ),
    (
        "string_with_conversion",
        doc(x={"address": 0, "type": "string", "count": 2, "multiplier": 2,
               "ha": {"platform": "sensor"}}),
        "string cannot be combined",
    ),
    (
        "float_with_flags",
        doc(x={"address": 0, "type": "float32", "flags": {0: "A"},
               "ha": {"platform": "sensor"}}),
        "floats cannot be combined",
    ),
    (
        "map_and_flags",
        doc(x={"address": 0, "map": {0: "a"}, "flags": {0: "A"},
               "ha": {"platform": "sensor"}}),
        "mutually exclusive",
    ),
    (
        "map_with_multiplier",
        doc(x={"address": 0, "map": {0: "a"}, "multiplier": 2,
               "ha": {"platform": "sensor"}}),
        "cannot be combined with multiplier",
    ),
    (
        "rmw_without_mask",
        doc(x={"address": 0, "read_modify_write": True,
               "ha": {"platform": "number", "min": 0, "max": 1}}),
        "requires a 'mask'",
    ),
    (
        "max_change_negative",
        doc(x={"address": 0, "max_change": -1, "ha": {"platform": "sensor"}}),
        "max_change must be >= 0",
    ),
    (
        "bad_entity_scan_interval",
        doc(x={"address": 0, "scan_interval": 0, "ha": {"platform": "sensor"}}),
        "scan_interval must be an integer",
    ),
    (
        "on_not_int",
        doc(x={"address": 0, "on_value": "x", "ha": {"platform": "switch"}}),
        "'on_value' must be an integer or boolean",
    ),
    (
        "write_value_bad_type",
        doc(x={"address": 0, "write_value": {"a": 1}, "ha": {"platform": "button"}}),
        "write_value must be a number",
    ),
    (
        "string_without_count",
        doc(x={"address": 0, "type": "string", "ha": {"platform": "sensor"}}),
        "strings require 'count'",
    ),
    (
        "string_with_sum_scale",
        doc(x={"address": 0, "type": "string", "count": 2, "sum_scale": [1, 2],
               "ha": {"platform": "sensor"}}),
        "sum_scale is not valid for strings",
    ),
    (
        "sum_scale_count_conflict",
        doc(x={"address": 0, "count": 3, "sum_scale": [1, 2],
               "ha": {"platform": "sensor"}}),
        "contradicts sum_scale",
    ),
    (
        "count_contradicts_type",
        doc(x={"address": 0, "type": "uint32", "count": 3, "ha": {"platform": "sensor"}}),
        "contradicts type",
    ),
    (
        "map_bad_key",
        doc(x={"address": 0, "map": {"a": "x"}, "ha": {"platform": "sensor"}}),
        "keys must be non-negative integers",
    ),
    (
        "flags_key_out_of_range",
        doc(x={"address": 0, "flags": {17: "x"}, "ha": {"platform": "sensor"}}),
        "out of range",
    ),
    (
        "map_not_dict",
        doc(x={"address": 0, "map": 5, "ha": {"platform": "sensor"}}),
        "'map' must be a non-empty mapping",
    ),
    (
        "bad_entity_category",
        doc(x={"address": 0, "ha": {"platform": "sensor", "entity_category": "diagnostics"}}),
        "is invalid",
    ),
    (
        "bad_device_class",
        doc(x={"address": 0, "ha": {"platform": "sensor", "device_class": "warmth"}}),
        "is invalid",
    ),
    (
        "button_without_write_value",
        doc(x={"address": 0, "ha": {"platform": "button"}}),
        "buttons require 'write_value'",
    ),
    (
        "write_value_on_sensor",
        doc(x={"address": 0, "write_value": 1, "ha": {"platform": "sensor"}}),
        "only valid for buttons",
    ),
    (
        "select_without_map",
        doc(x={"address": 0, "ha": {"platform": "select"}}),
        "selects require 'map'",
    ),
    (
        "select_map_not_unique",
        doc(x={"address": 0, "map": {0: "a", 1: "a"}, "ha": {"platform": "select"}}),
        "must be unique",
    ),
    (
        "text_without_string",
        doc(x={"address": 0, "ha": {"platform": "text"}}),
        "require type 'string'",
    ),
    (
        "number_without_min_max",
        doc(x={"address": 0, "ha": {"platform": "number"}}),
        "numbers require ha.min and ha.max",
    ),
    (
        "number_with_map",
        doc(x={"address": 0, "map": {0: "a"},
               "ha": {"platform": "number", "min": 0, "max": 1}}),
        "numbers cannot use map/flags",
    ),
    (
        "switch_with_string",
        doc(x={"address": 0, "type": "string", "count": 1, "ha": {"platform": "switch"}}),
        "plain numeric or bit value",
    ),
    (
        "on_off_on_sensor",
        doc(x={"address": 0, "on_value": 1, "ha": {"platform": "sensor"}}),
        "only valid for switch and binary_sensor",
    ),
    (
        "flags_on_button",
        doc(x={"address": 0, "write_value": 1, "flags": {0: "A"},
               "ha": {"platform": "button"}}),
        "only valid for sensors",
    ),
    (
        "mirror_on_sensor",
        doc(x={"address": 0, "duplicate_as_sensor": True, "ha": {"platform": "sensor"}}),
        "only makes sense for writable",
    ),
    (
        "write_on_read_only_table",
        doc("input", x={"address": 0, "ha": {"platform": "number", "min": 0, "max": 1}}),
        "read-only",
    ),
]


@pytest.mark.parametrize("data,match", [c[1:] for c in ERROR_CASES], ids=[c[0] for c in ERROR_CASES])
def test_error_branches(data, match):
    with pytest.raises(DeviceSchemaError, match=match):
        parse_device(data, "t.yaml")


TEMPLATE_ERROR_CASES = [
    (
        "bad_platform",
        {"x": {"state": "{{ 1 }}", "ha": {"platform": "vacuum"}}},
        "template platform must be one of",
    ),
    (
        "not_mapping",
        {"x": 5},
        "template entry must be a mapping",
    ),
    (
        "no_ha",
        {"x": {"state": "{{ 1 }}"}},
        "'ha:' block with a 'platform:'",
    ),
    (
        "unknown_keys",
        {"x": {"state": "{{ 1 }}", "wobble": 1, "ha": {"platform": "sensor"}}},
        "unknown sensor template keys",
    ),
    (
        "state_not_string",
        {"x": {"state": 5, "ha": {"platform": "sensor"}}},
        "must be a template string",
    ),
    (
        "missing_state",
        {"x": {"ha": {"platform": "sensor"}}},
        "'state' \\(a template string\\) is required",
    ),
    (
        "missing_action",
        {"x": {"state": "{{ 1 }}", "ha": {"platform": "switch"}}},
        "'turn_on' action is required",
    ),
    (
        "action_not_mapping",
        {"x": {"state": "{{ 1 }}", "turn_on": 5, "turn_off": {"entity": "t", "value": 0},
               "ha": {"platform": "switch"}}},
        "must be a mapping with an 'entity' key",
    ),
    (
        "action_unknown_keys",
        {"x": {"state": "{{ 1 }}", "turn_on": {"entity": "t", "value": 1, "foo": 2},
               "turn_off": {"entity": "t", "value": 0}, "ha": {"platform": "switch"}}},
        "unknown keys",
    ),
    (
        "action_unknown_entity",
        {"x": {"state": "{{ 1 }}", "turn_on": {"entity": "ghost", "value": 1},
               "turn_off": {"entity": "t", "value": 0}, "ha": {"platform": "switch"}}},
        "references unknown entity",
    ),
    (
        "action_read_only_target",
        {"x": {"state": "{{ 1 }}", "turn_on": {"entity": "ro", "value": 1},
               "turn_off": {"entity": "t", "value": 0}, "ha": {"platform": "switch"}}},
        "read-only 'input:' section",
    ),
    (
        "fixed_without_value",
        {"x": {"state": "{{ 1 }}", "turn_on": {"entity": "t"},
               "turn_off": {"entity": "t", "value": 0}, "ha": {"platform": "switch"}}},
        "needs a 'value'",
    ),
    (
        "mapped_map_empty",
        {"x": {"state": "{{ 1 }}", "select_option": {"entity": "t", "map": {}},
               "ha": {"platform": "select"}}},
        "must be a non-empty mapping",
    ),
    (
        "select_options_underivable",
        {"x": {"state": "{{ 1 }}", "select_option": {"entity": "t"},
               "ha": {"platform": "select"}}},
        "cannot determine the options",
    ),
    (
        "select_options_not_list",
        {"x": {"state": "{{ 1 }}", "options": 5, "select_option": {"entity": "t"},
               "ha": {"platform": "select"}}},
        "must be a non-empty list",
    ),
    (
        "climate_bad_hvac_mode",
        {"x": {"current_temperature": "{{ 1 }}", "hvac_modes": ["banana"],
               "ha": {"platform": "climate"}}},
        "is invalid",
    ),
    (
        "climate_bad_unit",
        {"x": {"current_temperature": "{{ 1 }}", "temperature_unit": "X",
               "ha": {"platform": "climate"}}},
        "is invalid",
    ),
    (
        "climate_mode_without_modes",
        {"x": {"current_temperature": "{{ 1 }}", "set_hvac_mode": {"entity": "t"},
               "ha": {"platform": "climate"}}},
        "needs 'hvac_modes'",
    ),
    (
        "fan_preset_without_modes",
        {"x": {"state": "{{ 1 }}", "preset_mode": "{{ 'eco' }}",
               "turn_on": {"entity": "t", "value": 1},
               "turn_off": {"entity": "t", "value": 0}, "ha": {"platform": "fan"}}},
        "fan presets need",
    ),
    (
        "cover_without_state",
        {"x": {"open_cover": {"entity": "t", "value": 1}, "ha": {"platform": "cover"}}},
        "covers need an 'is_closed' or 'position'",
    ),
    (
        "number_without_min_max",
        {"x": {"state": "{{ 1 }}", "set_value": {"entity": "t"},
               "ha": {"platform": "number"}}},
        "template numbers require ha.min and ha.max",
    ),
    (
        "switch_target_unknown_key",
        {"x": {"set_temperature": {"by": "{{ 1 }}", "cases": {"A": {"entity": "t"}},
                                   "bogus": 1}, "ha": {"platform": "climate"}}},
        "unknown keys",
    ),
    (
        "switch_target_empty_cases",
        {"x": {"set_temperature": {"by": "{{ 1 }}", "cases": {}},
               "ha": {"platform": "climate"}}},
        "non-empty",
    ),
    (
        "switch_target_missing_selector",
        {"x": {"set_temperature": {"cases": {"A": {"entity": "t"}}},
               "ha": {"platform": "climate"}}},
        "template string",
    ),
    (
        "switch_target_case_read_only",
        {"x": {"set_temperature": {"by": "{{ 1 }}", "cases": {"A": {"entity": "ro"}}},
               "ha": {"platform": "climate"}}},
        "read-only",
    ),
]


@pytest.mark.parametrize(
    "template,match",
    [c[1:] for c in TEMPLATE_ERROR_CASES],
    ids=[c[0] for c in TEMPLATE_ERROR_CASES],
)
def test_template_error_branches(template, match):
    data = {
        **DEVICE,
        "holding": {"t": {"address": 0, "ha": {"platform": "sensor"}}},
        "input": {"ro": {"address": 1, "ha": {"platform": "sensor"}}},
        "template": template,
    }
    with pytest.raises(DeviceSchemaError, match=match):
        parse_device(data, "t.yaml")


def test_switch_target_parses_cases():
    dev = parse_device(
        tdoc(klima={
            "ha": {"platform": "climate"},
            "target_temperature": "{{ setpoint }}",
            "set_temperature": {
                "by": "{{ mode }}",
                "cases": {"Auto": {"entity": "setpoint"}, "Off": {"entity": "temp"}},
            },
        }),
        "t.yaml",
    )
    (t,) = dev.templates
    st = t.config["set_temperature"]
    assert isinstance(st, SwitchTarget)
    assert st.selector == "{{ mode }}"
    assert set(st.cases) == {"Auto", "Off"}
    assert st.cases["Auto"].entity == "setpoint"


def test_static_value_parses():
    dev = parse_device(
        doc(pc={
            "address": 124, "static_value": "Off", "write_multiple": True,
            "map": {0: "Off", 1: "On"}, "ha": {"platform": "select"},
        }),
        "t.yaml",
    )
    e = dev.entities[0]
    assert e.static_value == "Off" and e.write_multiple and e.optimistic_default is None


def test_optimistic_default_parses():
    dev = parse_device(
        doc(pc={
            "address": 50, "optimistic_default": "Off",
            "map": {0: "Off", 1: "On"}, "ha": {"platform": "select"},
        }),
        "t.yaml",
    )
    e = dev.entities[0]
    assert e.optimistic_default == "Off" and e.static_value is None


@pytest.mark.parametrize("key", ["static_value", "optimistic_default"])
def test_write_only_default_requires_writable_platform(key):
    with pytest.raises(DeviceSchemaError, match=key):
        parse_device(doc(x={"address": 1, key: "x", "ha": {"platform": "sensor"}}), "t.yaml")


@pytest.mark.parametrize("key", ["static_value", "optimistic_default"])
def test_write_only_default_conflicts_with_read_register(key):
    with pytest.raises(DeviceSchemaError, match="mutually exclusive"):
        parse_device(
            doc(x={
                "address": 1, key: "a", "read_register": "{{ y }}",
                "map": {0: "a", 1: "b"}, "ha": {"platform": "select"},
            }),
            "t.yaml",
        )


def test_static_value_and_optimistic_default_conflict():
    with pytest.raises(DeviceSchemaError, match="mutually exclusive"):
        parse_device(
            doc(x={
                "address": 1, "static_value": "a", "optimistic_default": "b",
                "map": {0: "a", 1: "b"}, "ha": {"platform": "select"},
            }),
            "t.yaml",
        )


@pytest.mark.parametrize("key", ["static_value", "optimistic_default"])
@pytest.mark.parametrize("seed", [0, False, "None", "unavailable", "0", "Off"])
def test_write_only_default_preserves_falsy_and_special_seeds(key, seed):
    # the marker is "value present", not "value truthy": 0 / false / "None" /
    # "unavailable" are real seeds, shown as-is, not treated as absent
    dev = parse_device(
        doc(pc={"address": 1, key: seed, "map": {0: "a", 1: "b"}, "ha": {"platform": "select"}}),
        "t.yaml",
    )
    val = getattr(dev.entities[0], key)
    assert val == seed and type(val) is type(seed)


@pytest.mark.parametrize("key", ["static_value", "optimistic_default"])
def test_write_only_default_null_rejected(key):
    # a present-but-null seed is a likely mistake (it would silently do nothing)
    with pytest.raises(DeviceSchemaError, match=key):
        parse_device(
            doc(x={"address": 1, key: None, "map": {0: "a", 1: "b"}, "ha": {"platform": "select"}}),
            "t.yaml",
        )


def test_write_multiple_rejected_on_non_writable():
    with pytest.raises(DeviceSchemaError, match="write_multiple"):
        parse_device(
            doc(x={"address": 1, "write_multiple": True, "ha": {"platform": "sensor"}}), "t.yaml"
        )


def test_time_entity_parses():
    dev = parse_device(
        doc(t={"address": 104, "type": "time", "ha": {"platform": "time"}}), "t.yaml"
    )
    e = dev.entities[0]
    assert e.platform == "time" and e.type == "time" and e.count == 1


def test_time_two_register_parses():
    # SolaX EV charger form: hour in the first register, minute in the second
    dev = parse_device(
        doc(t={"address": 0x634, "type": "time", "count": 2, "ha": {"platform": "time"}}),
        "t.yaml",
    )
    e = dev.entities[0]
    assert e.type == "time" and e.count == 2


def test_time_count_over_two_rejected():
    with pytest.raises(DeviceSchemaError, match="time occupies one register"):
        parse_device(
            doc(t={"address": 1, "type": "time", "count": 3, "ha": {"platform": "time"}}),
            "t.yaml",
        )


def test_time_platform_requires_time_type():
    with pytest.raises(DeviceSchemaError, match="time entities require type"):
        parse_device(doc(t={"address": 1, "ha": {"platform": "time"}}), "t.yaml")


def test_time_type_requires_time_platform():
    with pytest.raises(DeviceSchemaError, match="only valid for the time platform"):
        parse_device(
            doc(t={"address": 1, "type": "time", "ha": {"platform": "sensor"}}), "t.yaml"
        )


def test_legacy_on_off_key_gets_pointed_hint():
    # 'on'/'off' are named on_value/off_value; unquoted on/off keys are YAML 1.1
    # booleans (the key parses as True/False), so both spellings get the hint
    for key in ("on", True):
        with pytest.raises(DeviceSchemaError, match="on_value"):
            parse_device(
                doc(x={"address": 0, key: 1, "ha": {"platform": "switch"}}), "t.yaml"
            )


def test_rectify_time_parses_on_time_entity():
    dev = parse_device(
        doc(t={"address": 1, "type": "time", "rectify_time": True, "ha": {"platform": "time"}}),
        "t.yaml",
    )
    assert dev.entities[0].rectify_time is True


def test_rectify_time_rejected_on_non_time():
    with pytest.raises(DeviceSchemaError, match="rectify_time"):
        parse_device(
            doc(x={"address": 1, "rectify_time": True, "ha": {"platform": "sensor"}}), "t.yaml"
        )


def test_internal_time_readback_allows_rectify_time():
    # a linked time's read-back mirror: internal, time-typed, byte-swapped (SolaX GEN4)
    dev = parse_device(
        doc(t={"address": 151, "type": "time", "swap": "byte", "rectify_time": True,
               "internal": True}),
        "t.yaml",
    )
    assert dev.entities[0].rectify_time is True
    assert dev.entities[0].swap == "byte"


def test_internal_rectify_time_requires_time_type():
    with pytest.raises(DeviceSchemaError, match="rectify_time"):
        parse_device(
            doc(t={"address": 151, "rectify_time": True, "internal": True}), "t.yaml"
        )


# --- entity groups -----------------------------------------------------------


def test_entity_groups_parse_and_dedup():
    dev = parse_device(
        doc(x={"address": 0, "groups": ["basic", "extra", "basic"], "ha": {"platform": "sensor"}}),
        "t.yaml",
    )
    assert dev.entities[0].groups == ("basic", "extra")


def test_all_is_an_ordinary_group_name():
    # nothing reserved about "all": a file may declare a group of that name
    dev = parse_device(
        doc(x={"address": 0, "groups": ["all"], "ha": {"platform": "sensor"}}), "t.yaml"
    )
    assert dev.entities[0].groups == ("all",)
    assert dev.group_names == ("all",)


def test_entity_without_groups_defaults_empty():
    dev = parse_device(doc(x={"address": 0, "ha": {"platform": "sensor"}}), "t.yaml")
    assert dev.entities[0].groups == ()


def test_groups_must_be_nonempty_string_list():
    with pytest.raises(DeviceSchemaError, match="non-empty list"):
        parse_device(doc(x={"address": 0, "groups": [], "ha": {"platform": "sensor"}}), "t.yaml")
    with pytest.raises(DeviceSchemaError, match="non-empty strings"):
        parse_device(doc(x={"address": 0, "groups": [1], "ha": {"platform": "sensor"}}), "t.yaml")


def test_template_groups_parse():
    data = {
        **DEVICE,
        "holding": {"x": {"address": 0, "ha": {"platform": "sensor"}}},
        "template": {
            "y": {
                "ha": {"platform": "sensor", "name": "Y"},
                "state": "{{ x }}",
                "groups": ["basic", "extra"],
            }
        },
    }
    dev = parse_device(data, "t.yaml")
    assert dev.templates[0].groups == ("basic", "extra")


def test_default_groups_parse_and_group_names():
    data = {
        "device": {"manufacturer": "Acme", "model": "X1", "default_groups": ["basic"]},
        "holding": {
            "x": {"address": 0, "groups": ["basic"], "ha": {"platform": "sensor"}},
            "y": {"address": 1, "groups": ["advanced"], "ha": {"platform": "sensor"}},
        },
    }
    dev = parse_device(data, "t.yaml")
    assert dev.default_groups == ("basic",)
    assert dev.group_names == ("basic", "advanced")  # first-seen order


def test_default_groups_unknown_group_rejected():
    data = {
        "device": {"manufacturer": "Acme", "model": "X1", "default_groups": ["nope"]},
        "holding": {"x": {"address": 0, "groups": ["basic"], "ha": {"platform": "sensor"}}},
    }
    with pytest.raises(DeviceSchemaError, match="name groups no entity uses"):
        parse_device(data, "t.yaml")


def test_default_groups_accepts_reserved_basic():
    # "basic" is always enabled, so it is a valid default even without any tags
    data = {
        "device": {"manufacturer": "Acme", "model": "X1", "default_groups": ["basic"]},
        "holding": {
            "x": {"address": 0, "groups": ["advanced"], "ha": {"platform": "sensor"}}
        },
    }
    assert parse_device(data, "t.yaml").default_groups == ("basic",)


def test_default_groups_all_needs_a_declared_group():
    # "all" is not reserved: as a default it must name a declared group like any other
    data = {
        "device": {"manufacturer": "Acme", "model": "X1", "default_groups": ["all"]},
        "holding": {
            "x": {"address": 0, "groups": ["advanced"], "ha": {"platform": "sensor"}}
        },
    }
    with pytest.raises(DeviceSchemaError, match="name groups no entity uses"):
        parse_device(data, "t.yaml")


# --- regressions: newly rejected combinations, alias error message -----------


def test_switch_with_map_rejected():
    with pytest.raises(DeviceSchemaError, match="plain numeric or bit value"):
        parse_device(
            doc(x={"address": 0, "map": {0: "Off", 1: "On"}, "ha": {"platform": "switch"}}),
            "t.yaml",
        )


def test_binary_sensor_with_map_rejected():
    with pytest.raises(DeviceSchemaError, match="plain numeric or bit value"):
        parse_device(
            doc(x={"address": 0, "map": {0: "No", 1: "Yes"},
                   "ha": {"platform": "binary_sensor"}}),
            "t.yaml",
        )


def test_writable_mask_without_rmw_rejected():
    # would raise NotWritableError on every write; catch it at parse time
    with pytest.raises(DeviceSchemaError, match="read_modify_write"):
        parse_device(
            doc(x={"address": 0, "mask": 0xFF,
                   "ha": {"platform": "number", "min": 0, "max": 10}}),
            "t.yaml",
        )


def test_sensor_mask_without_rmw_still_valid():
    dev = parse_device(
        doc(x={"address": 0, "mask": 0xFF, "ha": {"platform": "sensor"}}), "t.yaml"
    )
    assert dev.entities[0].mask == 0xFF


def test_button_list_write_value_with_mask_still_valid():
    # a list write_value bypasses the codec, so the mask stays decode-only
    dev = parse_device(
        doc(x={"address": 0, "mask": 0xFF, "write_value": [1, 2],
               "ha": {"platform": "button"}}),
        "t.yaml",
    )
    assert dev.entities[0].write_value == (1, 2)


def test_string_with_zero_offset_rejected():
    # offset 0 is still a conversion; truthiness must not let it slip through
    with pytest.raises(DeviceSchemaError, match="string cannot be combined"):
        parse_device(
            doc(x={"address": 0, "type": "string", "count": 2, "offset": 0,
                   "ha": {"platform": "sensor"}}),
            "t.yaml",
        )


def test_ha_field_error_lists_only_applicable_aliases():
    with pytest.raises(DeviceSchemaError, match="not a select entity field") as err:
        parse_device(
            doc(x={"address": 0, "map": {0: "A", 1: "B"},
                   "ha": {"platform": "select", "unit": "V"}}),
            "t.yaml",
        )
    valid = str(err.value).split("valid: ")[1].rstrip(")")
    names = {n.strip() for n in valid.split(",")}
    assert "unit" not in names  # aliases native_unit_of_measurement: not on selects
    assert "enabled_by_default" in names  # its target exists on every platform
