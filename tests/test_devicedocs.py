"""Guard: the generated devicedocs stay in sync with their generators.

``support/devicedocs/<folder>/registers.md`` and ``groups.md`` are build artifacts of
the device configs + ``sources.json`` + the device folder contents + the generator
code. Nothing re-runs the generators automatically, so they used to drift silently
whenever any of those inputs changed. This regenerates every page in memory and
compares it to the committed file — drift now fails loudly:

    .venv/bin/python support/converter/_common/build_registers_md.py
    .venv/bin/python support/converter/_common/build_groups_md.py

All inputs are committed (no upstream checkout needed), so this always runs."""

import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_DOCS = _ROOT / "support/devicedocs"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


registers_md = _load("build_registers_md", "support/converter/_common/build_registers_md.py")
groups_md = _load("build_groups_md", "support/converter/_common/build_groups_md.py")

_SOURCES = json.loads((_ROOT / "support/converter/_common/sources.json").read_text(encoding="utf-8"))
_DEVICES = registers_md.config_folders()
_IDS = [folder for _cfg, folder in _DEVICES]


@pytest.mark.parametrize(("cfg_name", "folder"), _DEVICES, ids=_IDS)
def test_registers_md_is_current(cfg_name, folder):
    generated = registers_md.gen_one(registers_md.CFG_DIR / cfg_name, folder, _SOURCES)
    committed = (_DOCS / folder / "registers.md").read_text(encoding="utf-8")
    assert generated == committed, (
        f"{folder}/registers.md is stale — re-run support/converter/_common/build_registers_md.py"
    )


@pytest.mark.parametrize(("cfg_name", "folder"), _DEVICES, ids=_IDS)
def test_groups_md_is_current(cfg_name, folder):
    generated = groups_md.gen_one(cfg_name, folder)
    path = _DOCS / folder / "groups.md"
    if generated is None:  # config uses no entity groups -> there must be no page
        assert not path.exists(), f"{folder}/groups.md exists but {cfg_name} has no groups"
        return
    committed = path.read_text(encoding="utf-8")
    assert generated == committed, (
        f"{folder}/groups.md is stale — re-run support/converter/_common/build_groups_md.py"
    )
