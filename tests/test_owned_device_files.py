"""Guard: each owned device's bundled config is reproduced from its device.yaml.

The owned devices (Dimplex, Pichler, SolaX) are generated straight from a
hand-maintained ``support/devicedocs/<slug>/device.yaml`` — no upstream import.
This rebuilds each config in memory from its device.yaml through the real augment
pipeline (the same path ``convert_all.py`` uses) and checks it matches the committed
file: same values and same entity order. It catches drift in either direction —
hand-editing the generated config, or editing device.yaml without regenerating.

All inputs are in-tree (no external checkout), so this always runs."""

import importlib.util
from pathlib import Path

import pytest
import yaml

from custom_components.modbus_connect.schema import parse_device

_ROOT = Path(__file__).resolve().parent.parent
_CONFIGS = _ROOT / "custom_components/modbus_connect/device_configs"
_DOCS = _ROOT / "support/devicedocs"
_SECTIONS = ("holding", "input", "coil", "discrete", "template")


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


aug = _load("augment", "support/converter/_common/augment.py")


@pytest.mark.parametrize("slug", aug.owned_slugs())
def test_owned_config_regenerates_from_device_yaml(slug):
    doc = aug.load(_DOCS / slug / "device.yaml")
    assert doc is not None, f"missing support/devicedocs/{slug}/device.yaml"
    ir = aug.intermediate_from_device_file(doc)
    # An owned device normally has no augment.yaml (policy is baked into device.yaml);
    # if one is present it still applies, exactly as write_owned does.
    aug.apply(ir, aug.load(_DOCS / slug / "augment.yaml"))
    aug.resolve_translations(ir, aug.load_shared_translations())
    regenerated = yaml.safe_load(aug.emit(ir, header="test"))

    parse_device(regenerated, filename=f"{slug}.yaml")  # still a legal device file

    committed = yaml.safe_load((_CONFIGS / f"{slug}.yaml").read_text())
    # values, keys, groups, structure (dict compare is order-independent)
    assert regenerated == committed
    # and the entity order in every section matches the shipped file
    for section in _SECTIONS:
        assert list(regenerated.get(section) or {}) == list(committed.get(section) or {}), (
            f"{slug}: {section} entity order drifted"
        )


def test_owned_devices_have_no_stale_augment_yaml():
    """Owned policy lives in device.yaml; a leftover augment.yaml would silently
    re-apply on top (and its add: ops would collide with device.yaml entities)."""
    for slug in aug.owned_slugs():
        assert not (_DOCS / slug / "augment.yaml").exists(), (
            f"{slug}: unexpected augment.yaml — fold its policy into device.yaml"
        )


def test_dimplex_committed_translations_resolve():
    """The shipped Dimplex catalog localizes the model, a group label, and the
    operating-mode enum. Loads the committed file directly, so it needs no source."""
    doc = yaml.safe_load((_CONFIGS / "dimplex-si-11tu.yaml").read_text(encoding="utf-8"))
    de = parse_device(doc, "dimplex-si-11tu.yaml", language="de")
    en = parse_device(doc, "dimplex-si-11tu.yaml", language="en")

    assert de.model == "Sole/Wasser-Wärmepumpe SI 11TU"       # German source
    assert en.model == "Brine/water heat pump SI 11TU"        # English translation
    assert (de.group_label("clock"), en.group_label("clock")) == ("Uhr", "Clock")

    mode_de = next(e for e in de.entities if e.key == "operating_mode").value_map
    mode_en = next(e for e in en.entities if e.key == "operating_mode").value_map
    assert mode_de[0] == "Sommer" and mode_en[0] == "Summer"
    assert mode_de[1] == "Auto" and mode_en[1] == "Automatic"
