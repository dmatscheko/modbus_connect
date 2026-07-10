"""The generated editor JSON Schema: fresh, sound, and matching the parser."""

import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO / "docs" / "device_files.schema.json"
DEVICE_DIR = REPO / "custom_components" / "modbus_connect" / "device_configs"

# The generator is a standalone script (like the converters), loaded by path.
_spec = importlib.util.spec_from_file_location(
    "build_json_schema", REPO / "support" / "build_json_schema.py"
)
_gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gen)


@pytest.fixture(scope="module")
def validator() -> jsonschema.Draft7Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    return jsonschema.Draft7Validator(schema)


def test_committed_schema_is_fresh():
    """docs/device_files.schema.json must match a fresh generator run.

    On failure: .venv/bin/python support/build_json_schema.py
    """
    assert SCHEMA_PATH.read_text(encoding="utf-8") == _gen.render()


def _stringify_keys(node):
    """YAML integer keys as a language server sees them (JSON: string keys)."""
    if isinstance(node, dict):
        return {
            str(key).lower() if isinstance(key, bool) else str(key): _stringify_keys(value)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_stringify_keys(value) for value in node]
    return node


BUNDLED = sorted(DEVICE_DIR.glob("*.yaml"))


@pytest.mark.parametrize("path", BUNDLED, ids=[p.name for p in BUNDLED])
def test_bundled_files_validate(validator, path: Path):
    data = _stringify_keys(yaml.safe_load(path.read_text(encoding="utf-8")))
    errors = [
        f"{error.json_path}: {error.message}" for error in validator.iter_errors(data)
    ]
    assert not errors, "\n".join(errors)


BAD_DOCS = {
    "modbus_typo": {
        "device": {"manufacturer": "A", "model": "X"},
        "holding": {"t": {"address": 1, "multiplyer": 2, "ha": {"platform": "sensor"}}},
    },
    "ha_typo": {
        "device": {"manufacturer": "A", "model": "X"},
        "holding": {"t": {"address": 1, "ha": {"platform": "sensor", "icom": "x"}}},
    },
    "bad_device_class": {
        "device": {"manufacturer": "A", "model": "X"},
        "holding": {
            "t": {"address": 1, "ha": {"platform": "sensor", "device_class": "warmth"}}
        },
    },
    "conversion_on_bit_table": {
        "device": {"manufacturer": "A", "model": "X"},
        "coil": {"t": {"address": 1, "multiplier": 2, "ha": {"platform": "switch"}}},
    },
    "field_of_other_platform": {
        "device": {"manufacturer": "A", "model": "X"},
        "holding": {"t": {"address": 1, "ha": {"platform": "sensor", "min": 1}}},
    },
    "template_missing_required": {
        "device": {"manufacturer": "A", "model": "X"},
        "holding": {"t": {"address": 1, "ha": {"platform": "sensor"}}},
        "template": {"x": {"ha": {"platform": "sensor"}}},
    },
}


@pytest.mark.parametrize("doc", BAD_DOCS.values(), ids=BAD_DOCS.keys())
def test_schema_rejects_mistakes(validator, doc):
    assert list(validator.iter_errors(doc)), "schema accepted a known-bad document"
