"""Guard: the Dimplex/Pichler configs are reproduced from source by their augment.yaml.

Each config is rebuilt in memory straight from its two sources — the modbus_local_gateway
upstream base + the manufacturer Modbus doc — then run through the real augment.yaml and
emitted. The result must be semantically identical to the committed file, with the same
entity order. This catches drift in either direction: editing a config by hand without
updating augment.yaml (or the source), or vice versa.

Needs a modbus_local_gateway checkout (``$MLG_GATEWAY_REPO`` or a sibling clone); the test
skips cleanly when it is absent."""

import importlib.util
from pathlib import Path

import pytest
import yaml

from custom_components.modbus_connect.schema import parse_device

_ROOT = Path(__file__).resolve().parent.parent
_CONFIGS = _ROOT / "custom_components/modbus_connect/device_configs"
_SECTIONS = ("holding", "input", "coil", "discrete", "template")


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


aug = _load("augment", "support/converter/_common/augment.py")
conv = _load("dimplex_pichler_convert", "support/converter/dimplex_pichler/dimplex_pichler-convert.py")


def _upstream_or_skip():
    try:
        return conv._upstream_dir()
    except SystemExit as exc:  # no modbus_local_gateway checkout available
        pytest.skip(str(exc))


@pytest.mark.parametrize("name", conv.DEVICES)
def test_config_is_regenerated_from_source(name):
    ir, _ = conv.build_intermediate(name, _upstream_or_skip())
    spec = aug.load(_ROOT / "support/converter" / name / "augment.yaml")
    assert spec is not None, f"missing augment.yaml for {name}"
    aug.apply(ir, spec)
    regenerated = yaml.safe_load(aug.emit(ir, header="test"))

    parse_device(regenerated, filename=f"{name}.yaml")  # still a legal device file

    committed = yaml.safe_load((_CONFIGS / f"{name}.yaml").read_text())
    # values, keys, groups, structure (dict compare is order-independent)
    assert regenerated == committed
    # and the entity order in every section matches the shipped file
    for section in _SECTIONS:
        assert list(regenerated.get(section) or {}) == list(committed.get(section) or {}), \
            f"{name}: {section} entity order drifted"
