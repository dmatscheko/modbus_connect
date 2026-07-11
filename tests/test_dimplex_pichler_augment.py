"""Guard: the Dimplex/Pichler augment.yaml files stay in sync with their configs.

Each config is re-augmented in memory (read config -> tag -> strip groups -> apply the
real augment.yaml -> emit -> parse) and must come back semantically identical to the
committed file. This catches drift in either direction: hand-editing a config's groups
without updating augment.yaml, or vice versa."""

import importlib.util
from pathlib import Path

import pytest
import yaml

from custom_components.modbus_connect.schema import parse_device

_ROOT = Path(__file__).resolve().parent.parent
_CONFIGS = _ROOT / "custom_components/modbus_connect/device_configs"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


aug = _load("augment", "support/converter/_common/augment.py")
conv = _load("dimplex_pichler_convert", "support/converter/dimplex_pichler/dimplex_pichler-convert.py")


@pytest.mark.parametrize("name", conv.DEVICES)
def test_config_is_a_fixpoint_of_its_augment_yaml(name):
    original = yaml.safe_load((_CONFIGS / f"{name}.yaml").read_text())
    spec = aug.load(_ROOT / "support/converter" / name / "augment.yaml")
    assert spec is not None, f"missing augment.yaml for {name}"

    ir = conv.config_to_intermediate(original)
    aug.apply(ir, spec)
    regenerated = yaml.safe_load(aug.emit(ir, header="test"))

    parse_device(regenerated, filename=f"{name}.yaml")  # still a legal device file

    def normalized(doc):
        out = {"device": {k: (sorted(v) if k == "default_groups" else v)
                           for k, v in (doc.get("device") or {}).items()}}
        for section in (*aug.TABLES, "template"):
            for key, fields in (doc.get(section) or {}).items():
                fields = dict(fields)
                if "groups" in fields:
                    fields["groups"] = sorted(fields["groups"])
                out[f"{section}.{key}"] = fields
        return out

    assert normalized(regenerated) == normalized(original)
