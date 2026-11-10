## What and why

<!-- One or two sentences. Link the issue if one exists. -->

## Checklist

- [ ] `pytest` (≥95% coverage), `ruff check`, and `mypy` pass locally
- [ ] New device file: tested against real hardware (state which), added as `support/devicedocs/<slug>/device.yaml` and generated with `convert_all.py --owned <slug>`
- [ ] Converter-derived files regenerated through the converter, not hand-edited
- [ ] `strings.json` changes mirrored to `translations/en.json` and `translations/de.json`
- [ ] Docs updated where behavior changed (`README.md` / `docs/device_files.md`)
