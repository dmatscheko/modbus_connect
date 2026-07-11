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
| `add` | append a new entity (`table:` + full definition; also `table: template`) |
| `remove` | delete matched entities |
| `set` | deep-merge fields into matched entities |
| `unset` | delete dotted paths (e.g. `ha.enabled_by_default`) from matched |
| `group` | union groups onto matched entities |
| `tag` / `untag` | mutate matched entities' tags (for multi-pass rules) |

`where` clauses: `key` / `not_key` / `key_matches`, `tag` / `tag_any` / `tag_all` /
`not_tag` / `tag_prefix` / `tag_matches`, `raw_name_matches`, `table`, `platform`,
`missing_group`. A `device:` block merges into device metadata (`default_groups`,
`group_labels`, …). See `tests/test_augment.py` for worked examples.

## Layout

```
support/converter/
├── convert_all.py                 # orchestrator: runs all converters in the right order
├── <device>/augment.yaml          # one per generated config — its grouping/patch policy
├── modbus_local_gateway/…-convert.py   # MLG device_configs      -> ~19 bundled configs
├── dimplex_pichler/…-convert.py        # re-augments the 3 curated Dimplex/Pichler configs
├── solax/…-convert.py                  # SolaX plugin            -> the 2 Solax_* configs
└── _common/
    ├── augment.py           # THE shared library + emitter + DSL (single writer)
    ├── build_registers_md.py# every config (+ sources.json) -> devicedocs/*/registers.md
    ├── build_groups_md.py   # every grouped config          -> devicedocs/*/groups.md
    ├── sources.json         # per-device primary-source metadata (for registers.md)
    ├── sources.py           # standalone parser for the downloaded manufacturer docs
    └── pichler_entities.py  # standalone: one Pichler xlsx row -> one entity dict
```

`sources.py` and `pichler_entities.py` are **standalone doc-parsing utilities** kept for
re-deriving registers from the manufacturer PDFs/spreadsheets; they are not part of the
regeneration pipeline (the Dimplex/Pichler extras they once produced are now curated
content in the bundled configs).

## Regenerate everything

```bash
# defaults assume the two upstream checkouts sit beside this repo
MLG_GATEWAY_REPO=/path/to/modbus_local_gateway \
SOLAX_MODBUS_REPO=/path/to/homeassistant-solax-modbus \
  .venv/bin/python support/converter/convert_all.py
```

Order matters and the orchestrator enforces it: `modbus_local_gateway` runs first and
**skips** Dimplex/Pichler (their base files exist upstream but are owned by the
specialized importer); `dimplex_pichler` then writes their enriched configs; `solax` runs
last. Every converter validates its output against the integration schema before writing.

### Run a single converter

```bash
# modbus_local_gateway  (old-format device_configs -> new format; skips Dimplex/Pichler)
.venv/bin/python support/converter/modbus_local_gateway/modbus_local_gateway-convert.py \
    /path/to/modbus_local_gateway/custom_components/modbus_local_gateway/device_configs \
    -o custom_components/modbus_connect/device_configs

# dimplex_pichler  (reads the 3 committed configs, re-applies their augment.yaml grouping)
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
