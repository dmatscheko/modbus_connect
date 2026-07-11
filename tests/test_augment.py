"""Unit tests for the common augmentation library (support/converter/_common/augment.py).

Covers every DSL verb and every ``where`` predicate, the canonical emitter (tag
stripping, mask hex, block/inline choices), and an end-to-end round-trip through the
integration schema."""

import importlib.util
from pathlib import Path

import pytest
import yaml

from custom_components.modbus_connect.schema import parse_device

_aug_path = (
    Path(__file__).resolve().parent.parent
    / "support" / "converter" / "_common" / "augment.py"
)
_spec = importlib.util.spec_from_file_location("augment", _aug_path)
aug = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aug)


def _ir():
    """A small tagged intermediate: two holding, one input, tagged for matching."""
    ir = aug.intermediate({"manufacturer": "Acme", "model": "X1"})
    aug.add_entity(ir, "holding", "cool_setpoint", tags={"raw-name:Kühlung Sollwert", "doc:extra"},
                   address=10, ha={"platform": "number", "name": "Kühlung Sollwert", "min": 0, "max": 40})
    aug.add_entity(ir, "holding", "solar_pump", tags={"raw-name:Solarpumpe", "doc:extra"},
                   address=11, ha={"platform": "switch", "name": "Solarpumpe"})
    aug.add_entity(ir, "input", "flow_temp", tags={"raw-name:Vorlauftemperatur", "internal"},
                   address=20, ha={"platform": "sensor", "name": "Vorlauftemperatur"})
    return ir


def _by_key(ir):
    return {e["key"]: e for _s, e in aug._iter(ir)}


# --- verbs ------------------------------------------------------------------ #
def test_group_by_raw_name_regex():
    ir = _ir()
    aug.apply(ir, {"ops": [{"group": ["cooling"], "where": {"raw_name_matches": r"K(ü|ue)hl"}}]})
    assert _by_key(ir)["cool_setpoint"]["groups"] == ["cooling"]
    assert "groups" not in _by_key(ir)["solar_pump"]


def test_group_is_union_not_replace():
    ir = _ir()
    aug.apply(ir, {"ops": [
        {"group": ["basic"], "where": {"key": "cool_setpoint"}},
        {"group": ["cooling"], "where": {"key": "cool_setpoint"}},
    ]})
    assert _by_key(ir)["cool_setpoint"]["groups"] == ["basic", "cooling"]


def test_add_and_remove():
    ir = _ir()
    aug.apply(ir, {"ops": [
        {"add": {"table": "holding", "key": "sync_clock", "address": 5006,
                 "write_value": ["{{ now().hour }}"], "groups": ["clock"],
                 "ha": {"platform": "button", "name": "Sync clock"}}},
        {"remove": True, "where": {"key": "solar_pump"}},
    ]})
    keys = _by_key(ir)
    assert "sync_clock" in keys and "solar_pump" not in keys
    assert keys["sync_clock"]["groups"] == ["clock"]


def test_add_after_and_before_position():
    ir = _ir()  # holding order: cool_setpoint, solar_pump
    aug.apply(ir, {"ops": [
        {"add": {"table": "holding", "key": "after_cool", "after": "cool_setpoint",
                 "address": 1, "ha": {"platform": "sensor", "name": "A"}}},
        {"add": {"table": "holding", "key": "at_front", "before": "cool_setpoint",
                 "address": 2, "ha": {"platform": "sensor", "name": "B"}}},
        {"add": {"table": "holding", "key": "at_end",
                 "address": 3, "ha": {"platform": "sensor", "name": "C"}}},
    ]})
    order = [e["key"] for _s, e in aug._iter(ir) if _s == "holding"]
    assert order == ["at_front", "cool_setpoint", "after_cool", "solar_pump", "at_end"]


def test_add_with_unknown_anchor_raises():
    ir = _ir()
    with pytest.raises(ValueError, match="anchor"):
        aug.apply(ir, {"ops": [{"add": {"table": "holding", "key": "x", "after": "nope",
                                         "address": 1, "ha": {"platform": "sensor", "name": "X"}}}]})


def test_emit_orders_ha_keys_canonically():
    ir = aug.intermediate({"manufacturer": "A", "model": "B"})
    # built in a deliberately non-canonical order (icon/enabled_by_default early, name late)
    aug.add_entity(ir, "input", "t", address=1, ha={
        "platform": "sensor", "enabled_by_default": False, "icon": "mdi:x",
        "state_class": "measurement", "device_class": "temperature",
        "unit_of_measurement": "°C", "name": "T"})
    lines = [ln.strip() for ln in aug.emit(ir).splitlines() if ln.startswith("      ")]
    keys = [ln.split(":", 1)[0] for ln in lines]
    assert keys == ["platform", "name", "unit_of_measurement", "device_class",
                    "state_class", "icon", "enabled_by_default"]


def test_set_deep_merges():
    ir = _ir()
    aug.apply(ir, {"ops": [{"set": {"ha": {"entity_category": "config"}},
                            "where": {"platform": "number"}}]})
    ha = _by_key(ir)["cool_setpoint"]["ha"]
    assert ha["entity_category"] == "config" and ha["name"] == "Kühlung Sollwert"  # merged, not replaced


def test_unset_dotted_path():
    ir = _ir()
    _by_key(ir)["solar_pump"]["ha"]["enabled_by_default"] = False
    aug.apply(ir, {"ops": [{"unset": ["ha.enabled_by_default"], "where": {"key": "solar_pump"}}]})
    assert "enabled_by_default" not in _by_key(ir)["solar_pump"]["ha"]


def test_tag_then_match_multipass():
    ir = _ir()
    aug.apply(ir, {"ops": [
        {"tag": ["writable"], "where": {"platform": ["number", "switch"]}},
        {"group": ["settings"], "where": {"tag": "writable"}},
    ]})
    assert _by_key(ir)["cool_setpoint"]["groups"] == ["settings"]
    assert _by_key(ir)["solar_pump"]["groups"] == ["settings"]
    assert "groups" not in _by_key(ir)["flow_temp"]


# --- where predicates ------------------------------------------------------- #
@pytest.mark.parametrize("where,expected", [
    ({"key": "cool_setpoint"}, {"cool_setpoint"}),
    ({"key": ["cool_setpoint", "solar_pump"]}, {"cool_setpoint", "solar_pump"}),
    ({"not_key": "flow_temp"}, {"cool_setpoint", "solar_pump"}),
    ({"key_matches": r"_setpoint$"}, {"cool_setpoint"}),
    ({"tag": "internal"}, {"flow_temp"}),
    ({"not_tag": "internal"}, {"cool_setpoint", "solar_pump"}),
    ({"tag_any": ["doc:extra", "nope"]}, {"cool_setpoint", "solar_pump"}),
    ({"tag_all": ["doc:extra", "raw-name:Solarpumpe"]}, {"solar_pump"}),
    ({"tag_prefix": "raw-name:"}, {"cool_setpoint", "solar_pump", "flow_temp"}),
    ({"tag_matches": r"^doc:"}, {"cool_setpoint", "solar_pump"}),
    ({"raw_name_matches": "Solar"}, {"solar_pump"}),
    ({"table": "input"}, {"flow_temp"}),
    ({"platform": "number"}, {"cool_setpoint"}),
    ({"missing_group": True}, {"cool_setpoint", "solar_pump", "flow_temp"}),
    (None, {"cool_setpoint", "solar_pump", "flow_temp"}),
])
def test_where_predicates(where, expected):
    ir = _ir()
    aug.apply(ir, {"ops": [{"tag": ["hit"], "where": where}]})
    assert {e["key"] for _s, e in aug._iter(ir) if "hit" in aug._tags(e)} == expected


def test_where_clauses_and_together():
    ir = _ir()
    aug.apply(ir, {"ops": [{"group": ["g"], "where": {"table": "holding", "platform": "switch"}}]})
    assert _by_key(ir)["solar_pump"].get("groups") == ["g"]
    assert "groups" not in _by_key(ir)["cool_setpoint"]  # holding but not switch


def test_missing_group_fallback_tiering():
    """basic first, then everything still ungrouped (and not internal) -> advanced."""
    ir = _ir()
    aug.apply(ir, {"ops": [
        {"group": ["basic"], "where": {"key": "cool_setpoint"}},
        {"group": ["advanced"], "where": {"missing_group": True, "not_tag": "internal"}},
    ]})
    keys = _by_key(ir)
    assert keys["cool_setpoint"]["groups"] == ["basic"]
    assert keys["solar_pump"]["groups"] == ["advanced"]
    assert "groups" not in keys["flow_temp"]  # internal stays ungrouped (expert)


def test_device_block_merged():
    ir = _ir()
    aug.apply(ir, {"device": {"default_groups": ["basic"], "group_labels": {"cooling": "Cooling"}}})
    assert ir["device"]["default_groups"] == ["basic"]
    assert ir["device"]["manufacturer"] == "Acme"  # preserved


def test_none_spec_is_noop():
    ir = _ir()
    assert aug.apply(ir, None) is ir


# --- emitter ---------------------------------------------------------------- #
def test_emit_strips_tags_and_metadata():
    ir = _ir()
    text = aug.emit(ir, header="hdr")
    assert "_tags" not in text and "raw-name" not in text and "doc:extra" not in text
    assert text.startswith("# hdr\n")


def test_emit_mask_as_hex_and_groups_inline():
    ir = aug.intermediate({"manufacturer": "A", "model": "B"})
    aug.add_entity(ir, "holding", "flags_reg", address=1, mask=0x0F, groups=["basic", "diag"],
                   ha={"platform": "sensor", "name": "Flags"})
    text = aug.emit(ir)
    assert "mask: 0xF" in text
    assert "groups: [basic, diag]" in text


def test_emit_map_block_and_write_value_sequence():
    ir = aug.intermediate({"manufacturer": "A", "model": "B"})
    aug.add_entity(ir, "holding", "mode", address=1, map={0: "Off", 1: "On"},
                   ha={"platform": "select", "name": "Mode"})
    aug.add_entity(ir, "holding", "sync", address=2, write_value=["{{ now().hour }}", "{{ now().minute }}"],
                   ha={"platform": "button", "name": "Sync"})
    text = aug.emit(ir)
    assert '    map:\n      0: "Off"\n      1: "On"\n' in text  # YAML 1.1 bool-likes quoted
    assert "    write_value:\n      - " in text


def test_round_trip_validates_against_schema():
    """emit -> parse_device: the canonical output is a legal device file."""
    ir = _ir()
    aug.apply(ir, {
        "device": {"default_groups": ["basic"], "group_labels": {"cooling": "Cooling"}},
        "ops": [
            {"group": ["basic"], "where": {"key": ["cool_setpoint", "flow_temp"]}},
            {"group": ["cooling"], "where": {"raw_name_matches": r"K(ü|ue)hl"}},
            {"set": {"ha": {"entity_category": "config"}}, "where": {"platform": "number"}},
        ],
    })
    text = aug.emit(ir, header="test")
    device = parse_device(yaml.safe_load(text), filename="test.yaml")
    entities = {e.key: e for e in device.entities}
    assert set(entities["cool_setpoint"].groups) == {"basic", "cooling"}
    assert device.default_groups == ("basic",)
    # tags did not survive into the parsed model or the text
    assert "_tags" not in text


# --- shared translation memory -------------------------------------------------

# A list of {lang: text} units, matched against a source string by any of its values.
_SHARED = [
    {"de": "Sommer", "en": "Summer"},
    {"de": "Auto", "en": "Automatic"},
    {"en": "Cooling", "de": "Kühlung"},
]


def _translations_ir():
    ir = aug.intermediate({"manufacturer": "Acme", "model": "Model X",
                           "group_labels": {"cooling": "Cooling", "x": "Custom Label"}})
    aug.add_entity(ir, "holding", "mode", address=1,
                   map={0: "Sommer", 1: "Auto", 9: "ObskurerModus"},
                   ha={"platform": "select", "name": "Betriebsart"})
    aug.add_entity(ir, "holding", "offset", address=2, map={0: "-5 °C", 1: "0 °C"},
                   ha={"platform": "select", "name": "Offset"})
    ir["translations"] = [{"de": "Model X", "en": "Model One"}]  # device-specific (the model)
    return ir


def test_shared_translations_applied_used_only():
    ir = _translations_ir()
    u_enum, u_names = aug.resolve_translations(ir, _SHARED)
    cat = ir["translations"]
    # model resolves from the device unit; enum + group label from shared (matched by value)
    assert cat["Model X"] == {"de": "Model X", "en": "Model One"}
    assert cat["Sommer"] == {"de": "Sommer", "en": "Summer"}
    assert cat["Auto"] == {"de": "Auto", "en": "Automatic"}
    assert cat["Cooling"] == {"en": "Cooling", "de": "Kühlung"}
    # untranslated used strings are reported, not emitted
    assert "ObskurerModus" not in cat and "ObskurerModus" in u_enum
    assert "Custom Label" not in cat and "Custom Label" in u_enum
    assert "Betriebsart" in u_names
    # pure numeric value labels are neither collected nor reported
    assert "-5 °C" not in cat and "-5 °C" not in u_enum


def test_shared_unit_matches_source_in_either_language():
    # a device whose source string is the ENGLISH value still finds the shared unit
    ir = aug.intermediate({"manufacturer": "Acme", "model": "M"})
    aug.add_entity(ir, "holding", "mode", address=1, map={0: "Summer"},
                   ha={"platform": "select"})
    aug.resolve_translations(ir, _SHARED)
    assert ir["translations"]["Summer"] == {"de": "Sommer", "en": "Summer"}


def test_device_translations_override_shared_per_language():
    ir = _translations_ir()
    # device unit shares 'Auto' with the shared unit, and overrides just the English
    ir["translations"] = [{"de": "Auto", "en": "Auto mode"}]
    aug.resolve_translations(ir, _SHARED)
    assert ir["translations"]["Auto"] == {"de": "Auto", "en": "Auto mode"}


def test_ambiguous_translation_value_warns(capsys):
    # the same value in two units with different text is ambiguous -> warn, keep first
    index = aug._translation_index(
        [{"de": "Kühlen", "en": "Cooling"}, {"en": "Cooling", "de": "Kühlung"}], "test "
    )
    assert "ambiguous" in capsys.readouterr().err
    assert index["Cooling"] == {"de": "Kühlen", "en": "Cooling"}  # first wins


def test_label_comparison_lint_flags_translated_literal():
    ir = _translations_ir()
    aug.add_entity(ir, "template", "clim", ha={"platform": "climate"},
                   hvac_mode="{{ 'x' if mode == 'Sommer' else 'y' }}",
                   hvac_action="{{ 'z' if key('mode') == 0 else 'w' }}")
    aug.resolve_translations(ir, _SHARED)
    hits = aug.label_comparisons_in_templates(ir, ir["translations"])
    # the '== Sommer' literal is flagged; the key('mode') == 0 comparison is not
    assert hits == {"clim": {"Sommer"}}


def test_load_shared_translations_is_a_list_matched_by_value():
    shared = aug.load_shared_translations()
    assert isinstance(shared, list)
    index = aug._translation_index(shared, "")
    # one unit, found from either language value
    assert index["Sommer"] == index["Summer"] == {"de": "Sommer", "en": "Summer"}
    assert index["Energy & runtime"]["de"] == "Energie & Laufzeit"
