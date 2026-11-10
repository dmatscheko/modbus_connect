# Contributing

Thanks for helping! Most contributions are one of three things:

- [Adding a device file](#adding-a-device-file) for hardware that is not
  supported yet
- [Changing a bundled device file](#changing-a-bundled-device-file)
- [Code changes](#code-changes)

Also here: [commit messages](#commit-messages) and
[reporting problems](#reporting-problems).

## Before you start

The commands below start with `.venv/bin/python` — the Python of a virtual
environment inside your checkout. It does not exist after a fresh clone;
create it once (Python 3.14 or newer is required):

```bash
git clone https://github.com/dmatscheko/modbus_connect   # or your fork
cd modbus_connect
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements_test.txt
```

[Development → Set up](docs/development.md#set-up) has the details (older
`python3`, Windows, updating).

## Adding a device file

A device file is one YAML file describing a device's registers and entities.
[Writing a device file](docs/writing_a_device_file.md) takes you from the
register list to a file that works in your own Home Assistant; the
[device file reference](docs/device_files.md) covers every key.

Once your file works, turn it into a bundled device:

1. Save it as `support/devicedocs/<slug>/device.yaml`, where `<slug>` is a
   lower-case `manufacturer-model` name such as `eastron-sdm630`. Keep the
   editor-schema line as its first line:

   ```yaml
   # yaml-language-server: $schema=https://raw.githubusercontent.com/dmatscheko/modbus_connect/main/docs/device_files.schema.json
   ```

2. Generate the bundled file and its reference pages from it:

   ```bash
   .venv/bin/python support/converter/convert_all.py --owned <slug>
   ```

   This writes `custom_components/modbus_connect/device_configs/<slug>.yaml`
   and the device's `registers.md` (and `groups.md` if the file uses groups).
   The files under `device_configs/` are generated — never place or edit one by
   hand.

   Optional, but valuable: put the manufacturer's register document (PDF,
   spreadsheet) into the same folder and describe it in
   `support/converter/_common/sources.json`. The generated `registers.md` then
   names the document the file was checked against.

3. Run the [checks](docs/development.md#run-the-checks). Every bundled file is
   parsed and schema-validated by CI.
4. Commit the `device.yaml` and the generated files together, and say in the
   pull request which hardware and firmware you tested against.

## Changing a bundled device file

Bundled files come in two kinds. Which one you have decides where to edit:

| Kind | Source of truth | How to change it |
| --- | --- | --- |
| **Owned** — every device with a `support/devicedocs/<slug>/device.yaml` (Anhui, Dimplex, Pichler, SolaX) | that `device.yaml` | edit it, then run `.venv/bin/python support/converter/convert_all.py --owned <slug>` |
| **Imported** — converted from a [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway) file | the upstream file plus `support/devicedocs/<slug>/augment.yaml` | fix the converter or the device's `augment.yaml` policy, then regenerate |

Either way, do not edit the output in `device_configs/`. Commit the source and
the regenerated files together: `tests/test_owned_device_files.py` and
`tests/test_devicedocs.py` fail when an output is stale.

**Imported files are untested.** Each one carries `untested: true` in its
`device:` block, which Home Assistant shows as *(untested)* after the model.
If you have the hardware and have verified the file, adopt the device — that
is what makes it *tested*:

1. Copy `custom_components/modbus_connect/device_configs/<slug>.yaml` to
   `support/devicedocs/<slug>/device.yaml` and delete the folder's
   `augment.yaml` (its policy is already part of the copied file).
2. Remove the generated header comment and the `untested: true` line, and
   correct whatever your testing turned up.
3. Run `.venv/bin/python support/converter/convert_all.py --owned <slug>`.
   From then on the importer skips the device, so an upstream change can no
   longer overwrite your work.
4. Move the device from the untested to the tested table in
   [`docs/supported_devices.md`](docs/supported_devices.md) and in the
   README, and say in the pull request which hardware and firmware you tested.

The [converter README](support/converter/README.md) explains the tooling,
including the full regeneration run for imported files.

## Code changes

[Development](docs/development.md) describes the code layout and the tooling.
With the environment from [before you start](#before-you-start) in place, the
checks are:

```bash
.venv/bin/python -m ruff check custom_components tests support
.venv/bin/python -m mypy
.venv/bin/python -m pytest tests/ \
    --cov=custom_components.modbus_connect --cov-fail-under=95
```

All three must pass; CI runs the same commands. Points worth knowing:

- `models.py`, `codec.py` and `planner.py` stay free of Home Assistant imports.
- `strings.json` is the translation source — mirror changes into
  `translations/en.json` (copy) and `translations/de.json` (translate).
- If you touch `schema.py`'s surface, regenerate the editor schema with
  `.venv/bin/python support/build_json_schema.py` (a test fails when it is
  stale).

## Commit messages

One line, imperative, lower-case — no body and no trailers (not even
`Co-Authored-By`). `git log --oneline` shows the house style:

- Start with a lower-case verb — `add`, `fix`, `move`, `rename`, `refactor`,
  `drop`, `bump`, `make`, …
- Say *what* changed, and *why* when it isn't obvious. One line, no trailing
  period; aim for < 80 chars, but a slightly longer line is fine.
- One logical change per commit; join tightly-related edits with `,` or `;`.
- Name things as they are — files (`README.md`), keys (`max_read_gap`,
  `on_value`), identifiers (`optimistic_default`), platforms (`valve`).

```
add device timeout, retries, and request_delay tuning
verify the device answers its Modbus ID during the config flow
make the all group implicit instead of tagging every entity
```

## Reporting problems

Use the [issue templates](https://github.com/dmatscheko/modbus_connect/issues/new/choose).
Attach the **diagnostics download** (device page → ⋮ → *Download diagnostics*):
it contains the parsed definition, the planning state and per-register failure
counts, and answers most questions in one attachment.
[Troubleshooting](docs/troubleshooting.md) may already have the answer.
