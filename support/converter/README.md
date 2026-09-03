# Converters & generators

Developer tooling that produces the bundled device files
(`custom_components/modbus_connect/device_configs/*.yaml`) and their generated
references (`registers.md`, `groups.md`) in [`support/devicedocs/`](../devicedocs/README.md).
None of it ships to users; it runs occasionally, from the repository's virtualenv:

```bash
.venv/bin/python support/converter/<script>.py
```

## Owned and imported devices

There are two kinds of bundled device:

- **Owned** (the tested ones — Anhui, Dimplex, Pichler, SolaX): the source of
  truth is a hand-maintained `support/devicedocs/<slug>/device.yaml`, in the same
  format as the emitted file. Edit it directly.
- **Imported** (the rest, from [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway)):
  converted from the upstream file, separating **facts** (where an entity came
  from, its raw name) from **policy** (grouping, field tweaks, translations).
  Facts are stamped as per-entity `tags` on an in-memory *tagged intermediate*;
  the policy is a declarative `support/devicedocs/<slug>/augment.yaml`.

Both flow through one shared library, so **every bundled file comes out in one
canonical style**, named after its docs folder (`<slug>`):

```
OWNED:     devicedocs/<slug>/device.yaml ─ augment.write_owned("<slug>") ─┐
IMPORTED:  upstream file ─ converter ─ tagged intermediate ─ write_augmented ┤
                                                                            ▼
           load devicedocs/<slug>/augment.yaml (absent → no policy) → apply ops
           → emit canonical YAML (tags stripped) → validate → device_configs/<slug>.yaml
```

The importer passes an upstream basename that `_common/device_folders.json` maps
to the slug (`SDM630` → `eastron-sdm630`); an owned device is identified by its
slug directly. Dropping a `device.yaml` into a folder makes that device owned: the
importer then skips it, so a re-import never clobbers hand curation.

### `_common/augment.py` — the single writer

The only code that writes a `device_configs/*.yaml`, with two entry points:
`write_augmented(ir, source_name, source=…, variant=…)` for imported devices and
`write_owned("<slug>")` for owned ones. It owns emit → validate → write,
including the file **header** (which names the converter and source, or the
`device.yaml`, and how to regenerate), so no converter formats YAML itself.
Register fields follow `ENTITY_FIELD_ORDER` and the keys of every `ha:` block
`HA_FIELD_ORDER`, so the output never depends on dict-insertion order.

The `augment.yaml` DSL is an ordered `ops:` list; each op is one verb plus an
optional `where` selector (clauses AND together):

| verb | effect |
|---|---|
| `add` | insert a new entity (`table:` + full definition; also `table: template`), positioned with `after:` / `before:` an existing key, else appended |
| `remove` | delete matched entities |
| `set` | deep-merge fields into matched entities |
| `unset` | delete dotted paths (`ha.enabled_by_default`, or `ha` for the whole block) from matched entities |
| `group` | union groups onto matched entities |
| `tag` / `untag` | mutate matched entities' tags (for multi-pass rules) |

`where` clauses: `key` / `not_key` / `key_matches`, `tag` / `tag_any` / `tag_all`
/ `not_tag` / `tag_prefix` / `tag_matches`, `raw_name_matches`, `table`,
`platform`, `missing_group`. A `device:` block merges into the device metadata
(`default_groups`, `group_labels`, …). `tests/test_augment.py` has worked examples.

### Translations

Human-facing strings (device model, group labels, entity and template names,
`map:`/`flags:` values) carry per-language text; the integration resolves them at
load against Home Assistant's language, falling back to English and then the
source string. Converter inputs are **lists of `{lang: text}` units**, matched to
a source string by **any** of their language values — one unit
`{de: Kühlen, en: Cool}` serves a German-sourced and an English-sourced device
alike. Two layers:

- `support/devicedocs/translations.yaml` — the shared translate-once memory
  (HVAC and domain vocabulary, group labels). Add a concept once; every device
  that uses any of its values gets it.
- per-device `translations:` — device-specific strings (the model) and
  overrides: a list of units in an imported device's `augment.yaml`, the resolved
  keyed block in an owned device's `device.yaml`. A device unit wins over a shared
  one that shares a value.

At emit time the library collects the strings each device actually uses and
writes **only those** into the file's `translations:` block, keyed by the source
string. It warns on stderr about used strings with no translation (the to-do
list), about any template that compares a *translated* label as a literal, and
about a value that maps to two different units (ambiguous — keep every value
unique: the mode is `Cool`, the group label `Cooling`). Templates must compare
the stable map key via `key('entity') == N`, never the label; see the climate
templates in the Dimplex and Pichler `device.yaml` files.

## Layout

```
support/converter/
├── convert_all.py                        # orchestrator: MLG import, then every owned device
├── modbus_local_gateway/…-convert.py     # upstream device_configs -> the imported configs
├── solax/…-convert.py                    # wills106 solax-modbus plugin -> new SolaX configs
│                                         #   (X3-Hybrid-G4 / X3-HAC are owned, so skipped)
└── _common/
    ├── augment.py                # the shared library: DSL, emitter, single writer
    ├── device_folders.json       # upstream basename -> devicedocs <slug>
    ├── build_registers_md.py     # every config (+ sources.json) -> devicedocs/*/registers.md
    ├── build_groups_md.py        # every grouped config          -> devicedocs/*/groups.md
    └── sources.json              # per-device primary-source metadata for registers.md
```

The per-device policy and docs live in [`support/devicedocs/<slug>/`](../devicedocs/README.md),
so nothing is duplicated between the two trees.

## Regenerate

```bash
# configs: only the MLG import needs an upstream checkout (defaults to a sibling clone)
MLG_GATEWAY_REPO=/path/to/modbus_local_gateway \
  .venv/bin/python support/converter/convert_all.py

# references, after the configs are final (folder names limit the run)
.venv/bin/python support/converter/_common/build_registers_md.py   # all     -> registers.md
.venv/bin/python support/converter/_common/build_groups_md.py      # grouped -> groups.md
```

To change an owned device, edit its `device.yaml` and run the three commands
(no checkout needed). Regeneration is cosmetic-only for imported files — keys,
addresses, groups and templates are unchanged — and every file validates against
the integration schema before it is written. `tests/test_devicedocs.py` fails
when a committed `registers.md` or `groups.md` is stale, and
`tests/test_owned_device_files.py` when an owned bundled file drifts from its
`device.yaml`.
