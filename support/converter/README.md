# Converters & generators

Developer tooling that produces the bundled device files
(`custom_components/modbus_connect/device_configs/*.yaml`) and their documentation
(`support/devicedocs/*/`). None of this ships to users; it is run occasionally to
(re)generate configs and docs.

Run everything with the repo's virtualenv interpreter. Its `pip` shebang is broken, but
the interpreter itself is fine:

```bash
.venv/bin/python support/converter/<script>.py
```

## Architecture: fact vs. policy

There are **two kinds of bundled device**:

- **Owned devices** (Dimplex, Pichler, SolaX) — their source of truth is a hand-maintained
  `support/devicedocs/<slug>/device.yaml`, in the same format as the emitted config. They
  are **not imported** from any other project; edit `device.yaml` directly.
- **Imported devices** (~19, from modbus_local_gateway) — converted from an upstream
  source, separating **facts** (where an entity came from, its raw name, …) from **policy**
  (grouping, field tweaks). Facts are stamped as a per-entity `tags` list on an in-memory
  *tagged intermediate*; policy lives in a declarative `support/devicedocs/<slug>/augment.yaml`.

Both kinds flow through one shared library that applies any policy and writes the file, so
**every bundled config comes out in one canonical style** and is named after its docs folder:

```
OWNED:     support/devicedocs/<slug>/device.yaml           (the source of truth)
             └─ augment.write_owned("<slug>")   ← reads device.yaml → intermediate
IMPORTED:  per-converter import (may handle many devices)
             └─ builds a TAGGED INTERMEDIATE (normal config + `tags` per entity)
                  └─ augment.write_augmented(ir, "<name>")
both →  the ONE writer: load support/devicedocs/<slug>/augment.yaml (absent → no policy)
        → apply ops → emit canonical YAML (tags stripped) → validate
        → write device_configs/<slug>.yaml
```

`<slug>` is the kebab-case docs folder **and** the output filename, so a device's config,
policy, and docs all share one name (`support/devicedocs/eastron-sdm630/…` →
`device_configs/eastron-sdm630.yaml`). The importer passes a source basename that
`_common/device_folders.json` maps to the slug (e.g. `SDM630` → `eastron-sdm630`); an owned
device is identified by its slug directly.

### `_common/augment.py` — the shared library (the single writer)

The only code that writes a `device_configs/*.yaml`. Two entry points:
`write_augmented(ir, source_name, source=…, variant=…)` for imported devices, and
`write_owned("<slug>")` for owned ones (it loads `device.yaml`, turns it into an
intermediate via `intermediate_from_device_file`, and calls `write_augmented(..., owned=True)`).
It owns emit → validate → write, so no converter formats YAML itself — including the file
**header**, which it composes in one canonical form. An imported device's header names the
converter variant, the source, and points to its `augment.yaml`; an owned device's header
points to its `device.yaml`. A converter may pass an optional `note` (an extra header line)
or `header=` to override the composed text entirely.

The `augment.yaml` DSL — an ordered `ops:` list, each op one verb plus an optional `where`
selector (all clauses AND together):

| verb | effect |
|---|---|
| `add` | insert a new entity (`table:` + full definition; also `table: template`). Optional `after:` / `before:` an existing key positions it; otherwise it appends |
| `remove` | delete matched entities |
| `set` | deep-merge fields into matched entities |
| `unset` | delete dotted paths (e.g. `ha.enabled_by_default`, or `ha` for the whole block) from matched |
| `group` | union groups onto matched entities |
| `tag` / `untag` | mutate matched entities' tags (for multi-pass rules) |

`where` clauses: `key` / `not_key` / `key_matches`, `tag` / `tag_any` / `tag_all` /
`not_tag` / `tag_prefix` / `tag_matches`, `raw_name_matches`, `table`, `platform`,
`missing_group`. A `device:` block merges into device metadata (`default_groups`,
`group_labels`, …). See `tests/test_augment.py` for worked examples.

### Translations (multi-language configs)

Human-facing strings (device model, group labels, entity/template names, `map:`/`flags:`
values) can carry per-language text. The integration resolves it at load against Home
Assistant's language, falling back to English then the source string. The converter inputs
are **lists of `{lang: text}` translation units**, each matched against a source string by
**any** of its language values — so one unit `{de: Kühlen, en: Cool}` serves both a
German-sourced device (map value `Kühlen`) and an English-sourced one (`Cool`), with no
duplicate entry. Two layers:

- **`support/devicedocs/translations.yaml`** — the shared **translate-once memory**. Add a
  concept's unit here once; the generator applies it to *every* device config that uses any
  of its values. Home for the shared HVAC/domain vocabulary (enum values, group labels).
- **per-device `translations:`** — device-specific strings (the model) and per-language
  overrides of a shared unit. For an imported device this is a **list** of `{lang: text}`
  units in its `augment.yaml`; for an owned device it is the resolved `translations:` block
  (keyed by source string) already in its `device.yaml`. A device unit overrides a shared
  one when they share a value.

At emit time `augment.py` collects the strings each device actually uses, looks each up in
the shared and device indexes (device wins per language), and writes **only those** into
the file's top-level `translations:` block — keyed by the actual source string, so the
integration's lookup is unchanged and no file carries a translation it does not need. It
**warns on stderr** about: used strings with no translation anywhere (the to-do list for
extending the memory); any template that still compares a *translated* label as a literal;
and any value that maps to two different units (**ambiguous** — keep every value unique, so
e.g. the mode is `Cool` and the group label is `Cooling`, both mapping to German cleanly).

That last warning matters: because a translated `map:`/`flags:` value changes what
templates see, a template must compare the stable map key via **`key('entity') == N`**,
never the label (`== 'Sommer'`). See `support/devicedocs/translations.yaml`, and the climate
templates in `devicedocs/dimplex-si-11tu/device.yaml` and `devicedocs/pichler-*/device.yaml`,
for worked examples. (`key()` needs a real mapped entity; a template-derived value like
Pichler's `aktuelle_luftungsstufe` has no map, so its labels stay literal and must not be
translated.)

The emitter writes one canonical style regardless of how a converter built its dicts:
register fields follow `ENTITY_FIELD_ORDER` and the keys inside every `ha:` block follow
`HA_FIELD_ORDER`, so the output never depends on dict-insertion order.

## Layout

The converter tree holds **only tooling** — the per-device grouping/patch policy lives with
that device's documentation under `support/devicedocs/<slug>/`, so there is no per-device
duplication between the two trees.

```
support/converter/                 # tooling only (no per-device folders)
├── convert_all.py                 # orchestrator: MLG import, then owned devices
├── modbus_local_gateway/…-convert.py   # MLG device_configs -> ~19 imported configs
├── solax/…-convert.py             # wills106 solax-modbus plugin -> NEW SolaX configs
│                                  #   (X3-Hybrid-G4 / X3-HAC are owned in-tree, so skipped)
└── _common/
    ├── augment.py             # THE shared library + emitter + DSL (single writer; write_owned)
    ├── device_folders.json    # source basename -> devicedocs <slug> (for the MLG import)
    ├── build_registers_md.py  # every config (+ sources.json) -> devicedocs/*/registers.md
    ├── build_groups_md.py     # every grouped config          -> devicedocs/*/groups.md
    └── sources.json           # per-device primary-source metadata (for registers.md)

support/devicedocs/
├── translations.yaml          # shared translate-once memory (source string -> {lang: text})
└── <slug>/                     # one folder per device — source/policy AND docs together
    ├── device.yaml            # OWNED devices: the hand-maintained source of truth
    ├── augment.yaml           # IMPORTED devices: grouping/patch policy (+ translations:)
    ├── registers.md            # generated register reference
    ├── groups.md               # generated entity-group reference
    ├── caveats.md              # hand-written notes (optional)
    └── <manufacturer doc>      # the source PDF/xlsx/html
```

A folder has **either** a `device.yaml` (owned) **or** an `augment.yaml` (imported), never
both — an owned device's policy is already baked into its `device.yaml`.

## Regenerate everything

```bash
# only the MLG import needs an upstream checkout (defaults to a sibling clone)
MLG_GATEWAY_REPO=/path/to/modbus_local_gateway \
  .venv/bin/python support/converter/convert_all.py
```

`modbus_local_gateway` runs first (it **skips** Dimplex/Pichler, whose base files exist
upstream but are owned in-tree); then each owned device is regenerated straight from its
`device.yaml` via `write_owned`. Every device validates against the integration schema
before writing.

### Run a single import

```bash
# modbus_local_gateway  (old-format device_configs -> new format; skips owned devices)
.venv/bin/python support/converter/modbus_local_gateway/modbus_local_gateway-convert.py \
    /path/to/modbus_local_gateway/custom_components/modbus_local_gateway/device_configs \
    -o custom_components/modbus_connect/device_configs
```

To change an **owned** device, edit its `support/devicedocs/<slug>/device.yaml` and re-run
`convert_all.py` (no checkout needed). Regeneration is **cosmetic-only** for imported files —
semantics (entity keys, addresses, groups, templates) are unchanged; a converter/emitter bug
fails schema validation loudly instead of at runtime.

## Documentation (configs → devicedocs)

Run **after** the configs are final. Both read the configs; `build_registers_md` also reads
`_common/sources.json` for the primary-source links.

```bash
.venv/bin/python support/converter/_common/build_registers_md.py   # all -> registers.md
.venv/bin/python support/converter/_common/build_groups_md.py      # grouped -> groups.md
```

Pass device-folder names to limit the run, e.g.
`build_registers_md.py dimplex-si-11tu pichler-lg150-lg250`. `caveats.md` in each device
folder is written by hand, not generated.
