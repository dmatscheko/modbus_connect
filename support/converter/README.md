# Converters & generators

Developer tooling that produces the bundled device files
(`custom_components/modbus_connect/device_configs/*.yaml`) and their
documentation (`support/devicedocs/*/`). None of this ships to users; it is
run occasionally to (re)generate configs and docs.

Run everything with the repo's virtualenv interpreter. Its `pip` shebang is
broken, but the interpreter itself is fine:

```bash
.venv/bin/python support/converter/<script>.py
```

Scripts that only parse source documents (`_common/sources.py`) are pure
standard library. The rest need **PyYAML**, which the Home Assistant venv
already provides.

## Layout

```
support/converter/
├── solax/
│   └── homeassistant_solax_modbus-convert.py   # SolaX plugin  -> Solax_X3_*.yaml
├── modbus_local_gateway/
│   └── modbus_local_gateway-convert.py         # MLG configs   -> ~20 bundled configs
└── _common/                                    # cross-device tooling I wrote
    ├── sources.py            # parse the downloaded manufacturer docs (xlsx / HTML)
    ├── pichler_entities.py   # one Pichler xlsx row -> one entity dict
    ├── expand_configs.py     # expand + feature-group the Dimplex / Pichler configs
    ├── build_registers_md.py # every config (+ sources.json) -> devicedocs/*/registers.md
    ├── build_groups_md.py    # every grouped config -> devicedocs/*/groups.md
    └── sources.json          # per-device primary-source metadata (for registers.md)
```

`_common/` holds the scripts that operate **across** devices (the registers.md
generator runs over all 23 configs; the expander handles both Dimplex and
Pichler; `sources.py`/`pichler_entities.py` are shared libraries), so they
cannot live in a single per-device folder — only the two upstream converters,
which each target one source project, do.

## Pipelines

### 1. Upstream conversion (source projects → device configs)

Regenerate the configs that were ported from the two Home Assistant upstream
projects. Independent of everything else; each reads an external checkout.

```bash
# SolaX  (needs a homeassistant-solax-modbus checkout + Home Assistant importable)
SOLAX_MODBUS_REPO=/path/to/homeassistant-solax-modbus \
  .venv/bin/python support/converter/solax/homeassistant_solax_modbus-convert.py

# modbus_local_gateway  (point it at the upstream device_configs, choose an output dir)
.venv/bin/python support/converter/modbus_local_gateway/modbus_local_gateway-convert.py \
  /path/to/modbus_local_gateway/custom_components/modbus_local_gateway/device_configs \
  -o custom_components/modbus_connect/device_configs
```

Both validate every file they emit through the integration's own schema, so an
emitter bug fails loudly instead of at runtime. Several MLG-derived files are
hand-edited afterwards (templates, tuning) — review a diff before overwriting.

### 2. Config expansion (Dimplex / Pichler → full grouped coverage)

`expand_configs.py` takes the three **curated** configs and expands them to full
primary-source coverage, tiered into entity groups (`basic` / `advanced` /
feature groups / untagged expert), and adds the Dimplex *Sync clock* button.
It reads the downloaded sources under `support/devicedocs/*/` via `sources.py`.

```bash
.venv/bin/python support/converter/_common/expand_configs.py
```

**Idempotent:** a config that already has `device.default_groups` is left
untouched, so this is a no-op on the current (already-expanded) files. To
regenerate from scratch, revert the config to its curated base first, e.g.

```bash
git checkout <curated-rev> -- custom_components/modbus_connect/device_configs/Dimplex-SI-11TU.yaml
.venv/bin/python support/converter/_common/expand_configs.py
```

The scaling rules are self-checked against the existing entries — run
`pichler_entities.py` directly and it must report **0 mismatches**:

```bash
.venv/bin/python support/converter/_common/pichler_entities.py
.venv/bin/python support/converter/_common/sources.py          # source-parser self-test
```

### 3. Documentation (configs → devicedocs)

Run **after** the configs are final. Both read the configs; `build_registers_md`
also reads `_common/sources.json` for the primary-source links.

```bash
.venv/bin/python support/converter/_common/build_registers_md.py   # all -> registers.md
.venv/bin/python support/converter/_common/build_groups_md.py      # grouped -> groups.md
```

Pass device-folder names to limit the run, e.g.
`build_registers_md.py dimplex-si-11tu pichler-lg150-lg250`.

`caveats.md` in each device folder is written by hand, not generated.

## Order

`1` (upstream conversion) and `2` (expansion) both change device configs, so run
them before `3` (docs). Within a normal edit you usually only touch one config
by hand and then re-run `3` to refresh its docs. Full rebuild order:

```
1. upstream converters      -> device_configs/*.yaml   (as needed)
2. expand_configs.py        -> Dimplex/Pichler configs (from their curated base)
3. build_registers_md.py + build_groups_md.py -> devicedocs/*/*.md
```
