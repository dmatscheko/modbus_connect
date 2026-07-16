# modbus-scanner — live register scanner with a web UI

A device-file authoring aid: point it at a gateway, watch its registers update on an
interval — dead/refused ones stay visible as greyed rows (write-only registers exist!),
or pick the **served** view to see only what answers — and *see* which ones change and
how fast (yellow → red heat) and what they might decode to. Then **map** registers by clicking them — name, platform, type, scale,
unit — and generate a device file from those mappings. All in the browser.

Unlike [`../modbus_cli.py`](../modbus_cli.py) (which imports nothing, to stay
copyable to any machine), this tool **reuses the integration's HA-free code** —
`planner.plan_blocks` for efficient, hole-skipping reads (the same block planning
the coordinator uses), `models` for the table/type vocabulary, and `schema` + `codec`
to validate each mapping and decode it exactly as the running integration would — so
its verdicts match runtime. Run it from the repo virtualenv.

## Run

```bash
.venv/bin/python support/modbus_scanner/scanner.py            # set the host in the UI
.venv/bin/python support/modbus_scanner/scanner.py --host <gateway> --device-id 1
.venv/bin/python support/modbus_scanner/scanner.py --demo     # simulated device, no hardware
```

Then open <http://127.0.0.1:8765> (opens automatically unless `--no-open`) and set the
**connection** — host / port / device id, or **Demo** — in the panel at the top, and hit
**Connect**; the scan controls stay disabled until you're connected. `--host` / `--demo` are
just shortcuts for that. **Demo** fakes a device (static config, a fast + slow counter, a
sine, a float32 ramp, and a couple of refused addresses) so you can try the whole UI with no
gateway.

Reconnecting **keeps** everything you've gathered — the per-register stats and history, the mapping,
and the dead-register list all survive a reconnect, so you can import a project and then connect
to watch it live without losing your work. **Clear all** (top row) is the one deliberate reset: it
drops the mapping, wipes every register's stats and history, and empties the dead-register list —
so registers earlier given up on as dead get re-probed from scratch on the next scan.

Everything else is set in the UI too — table, address range, per-read size (`max_register_read`),
and rescan interval. CLI flags (`--table` / `--start` / `--count` / `--max-read` / `--port` /
`--timeout` / `--retries` / `--web-port`) just seed the initial values.

The register list is laid out in two side-by-side columns, so twice as many rows fit on screen.
The **☰** button hides the settings block for the session (it always starts open). A browser
refresh restores everything the server knows: the view (table, position, tuning, filter, find),
the connection settings, the Manufacturer/Model stamp, and the picked device file. Everything else
lives in ONE **side panel** with three tabs — **Details** (value interpretations + history),
**Mapping** (the editor), **Generate** (the device file) — and a ✕ to close it. Exactly **one row
is selected** at a time (a crisp outline; the change-heat background stays untouched), and the open
panel always shows *that* row: click a data cell for Details, a **mapped as** / **decoded** cell
for Mapping — a click opens the panel, switches a wrong tab over, and a re-click on the same row's
cell closes it — or move the selection with **↑ / ↓** and the panel follows. Rows ticked for the
generated YAML carry a bold accent bar at their left edge (the whole checkbox cell is the click
target). Scan controls (Start/Stop, Scan once, interval) stay in the header so you can drive a scan
with the settings hidden, and the **◀ / ▶** buttons page the range backward / forward by exactly
the number of registers shown (with a live `start–end` readout between them), so you can walk a big
address space a screen at a time.

Tick **auto-page** and each scan steps to the *next* page on its own, wrapping back to the first at the
end of the table — so you can leave a scan running unattended and come back to a change map of the whole
table. Tick **＋ tables** as well and it carries on into the next table when one is done, cycling
holding → input → coil → discrete forever. (A wider **Count** sweeps faster; a **show** filter keeps the
sweep to just its matched registers — pick **served** for an unattended walk, since `all` pages through
the entire address space, dead registers included. A **Count** over 2000 asks for confirmation first — a
full unfiltered pass of that many registers is slow.)

## What you see

- **Change heat** — a register that changes lights up; the more often it changes,
  the redder it stays (and it flashes brighter on each change), so fast-changing
  live measurements stand out from static config/identity registers at a glance.
  The `rate` column is the share of that register's own reads in which it changed.
- **Dead registers stay visible** — `all` lists every known register, the refused ones included as
  greyed "not served" rows (write-only registers refuse every read, but they exist — and a device
  file's `bad_addresses:` show up the same way). A refused address (Modbus illegal-data-address) is
  retried once, then — after a **second** refusal in a row — given up on: dropped from the read plan
  for good; it stays *listed*, just never re-probed — each dead row has a small **↻** button to probe
  exactly that one register again (**Clear all** re-arms them all at once). The **served** view
  hides the dead ones instead — a **packed page** of only the registers the device answers, reading
  past the refused ones so the page always fills. Every view fills its page: **◀ / ▶** page through
  the matches and stop at the real ends, and near an edge the window slides the other way to top up
  rather than leave a half-empty screen.
- **Remembered across tables** — every value is kept per `(table, address)`, so a value's
  read/change counts and history survive switching table or paging away and back (and rescanning
  then flags anything that moved while you were elsewhere). Switching tables keeps your view
  **position** too, falling back to the first page when the switched-to table serves nothing there.
- **Filter the view** — the **show** menu narrows the page: **served**, only the registers the
  device answers (`all` minus the dead rows); just the *mapped* registers; just the
  *non-zero* ones; just the ones that have *changed* at least once (registers that moved between reads,
  once a sweep or two has run); or **mapped + changed**, the union of the two — everything you've mapped
  plus every register that's moving, a handy working set while you build the file. **x-ray** shows every
  register that *any* table maps: a same-width sibling's mapping (holding ↔ input, coil ↔ discrete)
  appears muted as if it were mapped here — decoded against *this* table's registers — and as a tiny
  top-right corner tag when the register also has its own mapping; the non-compatible tables' mappings
  show on hover. An unmapped register showing a sibling mapping also gets a small **⧉ copy** button —
  one click copies that mapping onto this table at this address (renamed with a table suffix, since
  display names must stay unique). Handy for spotting — and fixing — entities written against the
  wrong table. **x-ray + changed** adds every register that moved. **Count** sets how many rows a page
  shows in every view — `all` packs that many known registers, a filter that many matches. The scanned
  views (*served* / *non-zero* / *changed*) read forward or back as far as needed to fill the screen
  and stop where the device's map ends (`all` pages the whole address space); the *mapped* / *x-ray*
  views list a known set, so a mapped register is never missed — even one that sits far off or that
  the device refuses. The **find** box narrows any view further: comma-separated terms, each a
  mapping-name part (`heat`), an exact address (`40`, `0x28`), or an address range (`10-20`) — a
  register shows if *any* term matches, on top of the selected filter. Name terms search this
  table's mappings (in the x-ray views: *every* table's), and the fill probes only the matching
  candidates — a fresh or imported session finds a far register without scanning up to it. A fast way to find what
  matters in a big address space.
- **The Details tab** — click **any** of a register's data cells (address, value, hex, int16,
  Δ, rate) to open the side panel on **Details**. At the **top**, the "what type is this?" helper:
  the current value plus the uint/int/float/string interpretations of that register and the next few
  contiguous ones. **Below**, the last 50 *distinct* values it has taken — each with how long ago and
  at which scan it appeared, the Δ from the value before, and a sparkline — so a steadily-climbing
  energy meter reads differently from a noisy measurement at a glance. Hover any of those cells for a
  quick recent-values peek, and walk registers with **↑ / ↓** — the tab follows the selection. Paired
  with **auto-page**, an unattended run fills this history in across the whole device. (The
  **mapped as** and **decoded** cells open the **Mapping** tab instead.)

## Map registers

Two columns are always shown for mapping:

- **mapped as** — the entity mapped to that register (name + type); continuation registers
  of a multi-word entity show `↑ <name>`. Unmapped registers show a faint **＋ map**.
- **decoded** — the value that entity *would* decode there (scaling, enum map, float32, …),
  through the integration's own codec — exactly what the running integration would show.

Click either of a register's **mapped as** / **decoded** cells to open the editor (the side
panel's **Mapping** tab) and map it — moving the selection with **↑ / ↓** re-targets the open
editor to the newly selected register. The editor exposes what the
integration supports — name, platform (all nine), type/swap, scale/offset/sum_scale, mask, enum
map, flags, unit, device/state class, precision, category, icon, min/max/step, on/off, write_value
— plus an **advanced** block (YAML) for any other device-file key: `groups`, `scan_interval`, write
tuning, extra `ha:` fields, … Then **Save**. The mapping is validated by the
integration's real schema the instant you save: a bad combination (a `number` with no
min/max, a `select` with no map, …) is refused inline and your previous mapping is kept.
Click a mapped register to **edit** or **Unmap** it. Mappings live across all four tables at
once.

Two mistakes stand out while you work (or when testing a loaded file):

- a register the device **serves but nothing maps** → an amber `unmapped` badge (a gap to fill),
  right there in the plain view;
- a register a mapping points at but the device **refuses** → a red `refused ✕` badge (a wrong
  address — or a write-only register, which is fine). These show right in the `all` view; the
  *mapped* / *x-ray* views also list every mapped entity, dead addresses included (a multi-register
  entity keeps all its `↑` rows), so a mapping never disappears just because its register won't read.

### Load a device file

Pick a bundled config from the **Load a device file** dropdown (or **Upload…** your own, or
`--device <path-or-basename>` at startup) to load it *as the editable mapping* — test it
against the live device, then tweak entities and regenerate. Picking **— none —** drops the
active mapping but keeps everything else (stats, history, dead list). After an **Import**, the
dropdown gains an `imported · <manufacturer> <model>` entry: the session remembers that mapping —
edits included — so you can switch to a bundled file (or none) and back to it at any time; only
**Clear all** forgets it. The **fit range** buttons jump
the scan to exactly what it maps on each table, and the file's `bad_addresses:` list is applied
up front, so registers you already know are dead are skipped instead of re-probed.

## Export · import · generate

- **Export / Import** — save the whole **project** to JSON and reload it later to pick up where you
  left off (or hand it to someone else). It captures every table's per-register stats — last value,
  read count, change count, and the value **history** — the editable **mapping**, the **connection**
  settings, the Count / Per-read tuning, and the **Manufacturer / Model** stamp for generation. It
  deliberately does *not* save the table, scroll position, filter, or which bundled file was picked
  (the mapping itself is the project's), so loading a project doesn't yank you off whatever you're
  currently looking at.
- **Generate device file** (the side panel's **Generate** tab — the **Generate file…** button next
  to Export/Import opens it) — set manufacturer / model and get a **valid device file**:
  every entity you mapped, plus a bare sensor for each *ticked* (still-unmapped) served
  register — `state_class: measurement` on the ones that moved — plus a `bad_addresses:`
  hint. Only the refused registers the integration's planner can actually act on are
  written — one per gap *between* mapped registers, none outside the mapped range — so the
  file stays tiny (a couple of entries, not the tens of thousands a full scan refuses)
  while producing the exact same reads. Refine the rest by hand — see the
  [device-file reference](../../docs/device_files.md).
