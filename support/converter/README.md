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

Every converter separates **facts** (what it knows about each entity — where it came
from, its raw name, whether it is a raw internal reading) from **policy** (what to do
with it — grouping, field tweaks). Facts are stamped as a per-entity `tags` list on an
in-memory *tagged intermediate*; policy lives in a declarative
`support/converter/<device>/augment.yaml`. A single shared library applies the policy and
writes the file, so **every bundled config comes out in one canonical style**.

```
per-device converter (may handle many devices)
  └─ builds a TAGGED INTERMEDIATE in memory (normal config + `tags` per entity)
       └─ augment.write_augmented(ir, "<device>")   ← the ONE writer
            loads support/converter/<device>/augment.yaml  (absent → no policy)
            → applies its ops → emits canonical YAML (tags stripped) → validates
            → writes device_configs/<device>.yaml
```

`<device>` is the output basename: `support/converter/SDM630/augment.yaml` →
`device_configs/SDM630.yaml`.

### `_common/augment.py` — the shared library (the single writer)

The only code that writes a `device_configs/*.yaml`. Public entry point:
`write_augmented(ir, device_name, header=…)`. It owns emit → validate → write, so no
converter formats YAML itself.

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
Assistant's language, falling back to English then the source string. Two layers, both
`{source string: {lang: text}}`:

- **`_common/translations.yaml`** — the shared **translate-once memory**. Put a string's
  translation here once; the generator applies it to *every* device config that uses that
  string. This is the primary home for the shared HVAC/domain vocabulary (enum values,
  common group labels).
- **`<device>/augment.yaml` → `translations:`** — per-device entries that **override** the
  shared memory (per language), for a string that needs different text in one device.

At emit time `augment.py` collects the strings each device actually uses, resolves them
(shared, overridden by the device block), and writes **only those** into the file's
top-level `translations:` block — so no file carries a translation it does not need. It
then **warns on stderr** about used strings with no translation anywhere (the to-do list
for extending the memory), and about any template that still compares a *translated* label
as a literal.

That last warning matters: because a translated `map:`/`flags:` value changes what
templates see, a template must compare the stable map key via **`key('entity') == N`**,
never the label (`== 'Sommer'`). See `_common/translations.yaml`, and the migrated climate
templates in `Dimplex-SI-11TU/augment.yaml` and `Pichler-*/augment.yaml`, for worked
examples. (`key()` needs a real mapped entity; a template-derived value like Pichler's
`aktuelle_luftungsstufe` has no map, so its labels stay literal and must not be translated.)

The emitter writes one canonical style regardless of how a converter built its dicts:
register fields follow `ENTITY_FIELD_ORDER` and the keys inside every `ha:` block follow
`HA_FIELD_ORDER`, so the output never depends on dict-insertion order.

## Layout

```
support/converter/
├── convert_all.py                 # orchestrator: runs all converters in the right order
├── <device>/augment.yaml          # one per generated config — its grouping/patch policy
├── modbus_local_gateway/…-convert.py   # MLG device_configs      -> ~19 bundled configs
├── dimplex_pichler/…-convert.py        # MLG base + manufacturer docs -> the 3 Dimplex/Pichler configs
├── solax/…-convert.py                  # SolaX plugin            -> the 2 Solax_* configs
└── _common/
    ├── augment.py             # THE shared library + emitter + DSL (single writer)
    ├── translations.yaml      # shared translate-once memory (source string -> {lang: text})
    ├── dimplex_pichler_gen.py # manufacturer doc (xlsx/html) -> the Dimplex/Pichler expansion entities
    ├── build_registers_md.py  # every config (+ sources.json) -> devicedocs/*/registers.md
    ├── build_groups_md.py     # every grouped config          -> devicedocs/*/groups.md
    ├── sources.json           # per-device primary-source metadata (for registers.md)
    ├── sources.py             # parsers for the downloaded manufacturer docs (xlsx / html)
    └── pichler_entities.py    # one Pichler LS-Control xlsx row -> one entity dict
```

`sources.py` and `pichler_entities.py` parse the manufacturer documents under
`support/devicedocs/`; `dimplex_pichler_gen.py` drives them to build the Dimplex/Pichler
register expansion (see below). Run `pichler_entities.py` directly for its scaling
self-test (it must report 0 mismatches against the committed configs).

## Regenerate everything

```bash
# defaults assume the two upstream checkouts sit beside this repo
MLG_GATEWAY_REPO=/path/to/modbus_local_gateway \
SOLAX_MODBUS_REPO=/path/to/homeassistant-solax-modbus \
  .venv/bin/python support/converter/convert_all.py
```

Order matters and the orchestrator enforces it: `modbus_local_gateway` runs first and
**skips** Dimplex/Pichler (their base files exist upstream but are owned by the
specialized importer); `dimplex_pichler` then regenerates them from source (that same
upstream base + the manufacturer Modbus docs); `solax` runs last. Every converter
validates its output against the integration schema before writing.

### Run a single converter

```bash
# modbus_local_gateway  (old-format device_configs -> new format; skips Dimplex/Pichler)
.venv/bin/python support/converter/modbus_local_gateway/modbus_local_gateway-convert.py \
    /path/to/modbus_local_gateway/custom_components/modbus_local_gateway/device_configs \
    -o custom_components/modbus_connect/device_configs

# dimplex_pichler  (MLG upstream base + manufacturer docs -> the 3 configs; needs MLG_GATEWAY_REPO)
.venv/bin/python support/converter/dimplex_pichler/dimplex_pichler-convert.py

# solax  (needs a homeassistant-solax-modbus checkout; SOLAX_MODBUS_REPO or default path)
.venv/bin/python support/converter/solax/homeassistant_solax_modbus-convert.py
```

Regeneration is **cosmetic-only** for the shipped files — semantics (entity keys,
addresses, groups, templates) are unchanged; a converter/emitter bug fails schema
validation loudly instead of at runtime. Grouping and per-device tweaks are edited in the
device's `augment.yaml`, never in a converter.

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
