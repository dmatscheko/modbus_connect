# Development

How the code is organised, how to run the checks, and what the tooling under
`support/` does. For the contribution workflow — device files, commit
messages, reporting problems — see [CONTRIBUTING](../CONTRIBUTING.md).

- [Set up](#set-up)
- [Run the checks](#run-the-checks)
- [Code layout](#code-layout)
- [Tooling under `support/`](#tooling-under-support)
- [Translations](#translations)
- [Quality scale](#quality-scale)
- [Releases](#releases)
- [Design notes](#design-notes)

## Set up

Every command in this project's documentation starts with `.venv/bin/python`.
That is the Python interpreter of a virtual environment inside your checkout.
**It does not exist after a fresh clone** — create it once:

```bash
git clone https://github.com/dmatscheko/modbus_connect
cd modbus_connect
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements_test.txt
```

- **Python 3.14 or newer is required**, as it is by Home Assistant itself.
  Check with `python3 --version`. If your `python3` is older, install Python
  3.14 and create the environment with `python3.14 -m venv .venv` instead.
- The last command installs Home Assistant, pymodbus and the test tools into
  `.venv/` only; nothing is installed system-wide. `.venv/` is ignored by git.
- On Windows the interpreter is `.venv\Scripts\python.exe`; use it wherever
  these pages write `.venv/bin/python`.
- To bring the environment up to date later, run
  `.venv/bin/python -m pip install -U -r requirements_test.txt`.

## Run the checks

```bash
.venv/bin/python -m ruff check custom_components tests support
.venv/bin/python -m mypy                                   # strict, see pyproject.toml
.venv/bin/python -m pytest tests/ \
    --cov=custom_components.modbus_connect --cov-fail-under=95
```

All three must pass; CI (`.github/workflows/test.yml`) runs the same commands
on every push to `main` and every pull request.

## Code layout

Everything lives in `custom_components/modbus_connect/`:

| Module | Role |
| --- | --- |
| `models.py` | Plain dataclasses for devices, entities and read spans |
| `codec.py` | Registers ↔ values (pure) |
| `planner.py` | Block-read planning (pure) |
| `client.py` | The pymodbus wrapper: one shared connection per gateway or serial port |
| `schema.py` | Validates a device file's YAML and builds the models |
| `loader.py` | Finds and loads device files (bundled and user) |
| `coordinator.py` | Polling, cache, backoff, quarantine, writes |
| `entity.py` + platform modules | Thin entity classes, including the template-driven `climate.py`, `fan.py`, `cover.py`, `light.py` |
| `config_flow.py` | Setup, reconfigure and options dialogs |
| `diagnostics.py`, `issues.py` | The diagnostics download and repair issues |
| `device_configs/` | The bundled device files — **generated**, see below |

`models.py`, `codec.py` and `planner.py` have no Home Assistant imports and are
tested standalone. `tests/test_e2e_server.py` proves the transaction counts
against a real TCP server.

The device-file format these modules implement is documented in the
[device file reference](device_files.md); what the runtime does with it is
described in [how it works](how_it_works.md).

## Tooling under `support/`

None of this ships to users.

| Tool | What it is for |
| --- | --- |
| [`modbus_scanner/`](../support/modbus_scanner/README.md) | Browser-based register scanner for writing and testing device files against a live device |
| `modbus_cli.py` | Single-file terminal tool for probes, reads, writes and range scans (`--help`) |
| [`converter/`](../support/converter/README.md) | Generates the bundled device files and their reference pages |
| [`devicedocs/`](../support/devicedocs/README.md) | One folder per bundled device: its source, its manufacturer document, and the generated `registers.md` / `groups.md` |
| `build_json_schema.py` | Regenerates the editor schema for device files, [`docs/device_files.schema.json`](device_files.schema.json) |
| `brand/` | SVG sources and `build_brand.py` for the PNGs in `custom_components/modbus_connect/brand/`, which Home Assistant serves locally |

Two generated artifacts are guarded by tests, so a stale one fails CI:

- **Bundled device files and their docs.** The files in `device_configs/` are
  generated from `support/devicedocs/` and never edited by hand; see
  [CONTRIBUTING](../CONTRIBUTING.md#changing-a-bundled-device-file).
- **The editor schema.** After touching the surface of `schema.py`, run
  `.venv/bin/python support/build_json_schema.py`.

## Translations

`strings.json` is the source for the integration's own UI texts. Mirror every
change into `translations/en.json` (an exact copy) and `translations/de.json`
(translated).

Texts inside device files — entity names, option labels — are translated
separately; see the [converter README](../support/converter/README.md#translations).

## Quality scale

Custom integrations cannot carry an official quality scale rating (the manifest
says `custom`), but the code follows the
[integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
up to and including the **Platinum** rules: connection test before setup,
reconfigure flow, translations (English and German), translated exceptions,
diagnostics, parallel-update limits, strict typing, async I/O throughout, and
98% test coverage.

[`quality_scale.yaml`](../custom_components/modbus_connect/quality_scale.yaml)
documents every rule, including the exemptions (Modbus has no discovery, no
authentication, and no fixed entity set to translate).

## Releases

Releases are cut from the GitHub **Actions** tab: run the *Release* workflow
and enter the version (for example `0.7.0`). It

1. re-runs the full gate (ruff, mypy, tests),
2. bumps `manifest.json` and `pyproject.toml` when the version is new,
3. tags `vX.Y.Z`,
4. publishes a GitHub release with generated notes — the version HACS then
   offers to users.

## Design notes

- [Controller-style extensions](../support/controller_extensions.md) — why a
  continuously running control loop (the worked example is SolaX's mode 8/9
  power control) does not fit a declarative device file, what can be done
  today, and a sketch of first-class support.
