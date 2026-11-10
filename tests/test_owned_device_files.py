"""Guard: each owned device's bundled config is reproduced from its device.yaml.

The owned devices (every ``support/devicedocs/<slug>/`` with a ``device.yaml``) are
generated straight from that hand-maintained file — no upstream import. This
regenerates each config through ``write_owned`` (the call ``convert_all.py`` makes)
into a scratch directory and checks it equals the committed file byte for byte,
header included. It catches drift in either direction — hand-editing the generated
config, or editing device.yaml (or the generator) without regenerating.

All inputs are in-tree (no external checkout), so this always runs."""

import importlib.util
from pathlib import Path

import pytest
import yaml

from custom_components.modbus_connect.schema import parse_device

_ROOT = Path(__file__).resolve().parent.parent
_CONFIGS = _ROOT / "custom_components/modbus_connect/device_configs"
_DOCS = _ROOT / "support/devicedocs"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


aug = _load("augment", "support/converter/_common/augment.py")


@pytest.mark.parametrize("slug", aug.owned_slugs())
def test_owned_config_regenerates_from_device_yaml(slug, tmp_path):
    # write_owned emits, validates the result as a device file, and writes it.
    aug.write_owned(slug, dest_dir=tmp_path)
    regenerated = (tmp_path / f"{slug}.yaml").read_text(encoding="utf-8")
    committed = (_CONFIGS / f"{slug}.yaml").read_text(encoding="utf-8")
    assert regenerated == committed, (
        f"{slug}: regenerate with support/converter/convert_all.py --owned {slug}"
    )


def test_exactly_the_imported_configs_are_marked_untested():
    """Tested means owned: a bundled file says ``untested: true`` exactly when it
    is an import no device.yaml stands behind (the example file aside). Adopting
    a device removes the mark; nothing else may."""
    owned = set(aug.owned_slugs())
    for path in sorted(_CONFIGS.glob("*.yaml")):
        if path.stem == "test":
            continue
        device = yaml.safe_load(path.read_text(encoding="utf-8"))["device"]
        assert device.get("untested", False) is (path.stem not in owned), path.name


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
