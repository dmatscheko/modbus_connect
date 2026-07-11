# Contributing

Thanks for helping! Two kinds of contributions cover most needs: **device
files** for new hardware, and **code changes**.

## Device files

A device file is one YAML file describing a device's registers and entities —
the [device file reference](docs/device_files.md) covers the format, and the
bundled files in
[`custom_components/modbus_connect/device_configs/`](custom_components/modbus_connect/device_configs/)
are working examples.

Workflow that has worked well:

1. Start from the register documentation (manual, vendor PDF/XLS).
2. Put this as the file's first line for editor autocomplete and validation:

   ```yaml
   # yaml-language-server: $schema=https://raw.githubusercontent.com/dmatscheko/modbus_connect/main/docs/device_files.schema.json
   ```

3. Poke the real device with the standalone CLI while writing —
   `python3 support/modbus_cli.py --host <gateway> --help` (probe, read with
   decoded views, write, scan; needs only pymodbus). `scan` prints
   `bad_addresses:`/`split_before:` hints ready to paste.
4. Drop the file into `<ha_config>/modbus_connect/` and add the integration —
   schema errors name the entity and reason, right in the config flow.
5. For the PR: place the file in `device_configs/`, run the test suite (every
   bundled file is parsed and schema-validated by CI), and mention what
   hardware/firmware it was tested against.

Files converted from another integration's format belong with their
converter under `support/converter/`:
`support/converter/modbus_local_gateway/modbus_local_gateway-convert.py` and
`support/converter/solax/homeassistant_solax_modbus-convert.py` regenerate most
bundled files — if your file is derived from one of those sources, prefer fixing
the converter over hand-editing the output (hand-edited files are the exception
and are listed in the converters' headers). See `support/converter/README.md`
for the full tooling (config expansion, doc generation).

## Code changes

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/python -m pytest tests/ --cov=custom_components.modbus_connect  # gate: ≥95%
.venv/bin/ruff check custom_components tests converter support
.venv/bin/mypy custom_components/modbus_connect                           # strict
```

All three must pass; CI runs the same commands. Points worth knowing:

- Layout and module boundaries are described at the end of the
  [README](README.md#development); `models.py`/`codec.py`/`planner.py` stay
  free of Home Assistant imports.
- `strings.json` is the translation source — mirror changes into
  `translations/en.json` (copy) and `translations/de.json` (translate).
- If you touch `schema.py`'s surface, regenerate the editor schema:
  `.venv/bin/python support/build_json_schema.py` (a test fails when stale).

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

Use the issue templates — the **diagnostics download** (device page → ⋮ →
*Download diagnostics*) contains the parsed definition, planning state, and
per-register failure counts, and answers most questions in one attachment.
