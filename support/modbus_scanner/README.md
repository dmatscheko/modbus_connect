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

Connecting also sends one **probe read**, because a Modbus gateway accepts the TCP connection
for *any* Device ID — only a read reveals whether something answers behind it. Any answer (data,
or a Modbus exception like *illegal data address*) proves a device is there; silence, or a
gateway *target failed to respond* exception, shows a ⚠ warning right in the header — "no answer
from device ID 1 — check the Device ID" — while staying connected, since the device might just
be offline. The probe retries once (slow serial sides often miss the very first read), and the
warning **self-heals**: any later real answer clears it. During scanning the header stays honest
the same way — the value shown and the warning can never disagree: an operation where *nothing*
answered says "no answer"; one where some reads answered and some timed out is a **slow** link
(with a hint to raise Timeout), not a dead one; one that fully answers clears the
banner. And an unreadable stretch is never mistaken for the map's end — see paging, below.

Once connected the button turns into **Disconnect** (and the connection fields lock until you
drop the link — so what's shown is always what's connected). Disconnecting — like reconnecting —
**keeps** everything you've gathered: the per-register stats and history, the mapping, and the
dead-register list all survive, so you can import a project and then connect to watch it live
without losing your work (or drop the link and keep working with the frozen values). **Clear all** (top row) is the one deliberate reset: it
drops the mapping, wipes every register's stats and history, and empties the dead-register list —
so registers earlier given up on as dead get re-probed from scratch on the next scan.

The connection row's **Give up after** (the `--retries` flag / `retries` field) is how many
consecutive failed reads bury a non-responding register onto the dead list (default 2): raise it
to tolerate a flaky link, lower it to isolate truly-dead registers in fewer scans. It is *not* a
per-request retry — the scanner already re-tries a transient timeout on its own (and pymodbus's
own retry is left off), so this only sets the give-up threshold.

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
address space a screen at a time. The **Start** field always shows the first register on the page,
so it reads as "where am I" — and editing it and hitting **Apply range** *jumps* there, anchoring
the page at that address (a fast way to leap over a big unreadable stretch instead of paging through
it). ◀ / ▶ are enabled purely by the address bounds — ▶ while the last shown register is below the
top of the space, ◀ while the first is above 0 — with no probe past the page to decide it.

Tick **auto-page** and each scan steps to the *next* page on its own, wrapping back to the first at the
end of the table — so you can leave a scan running unattended and come back to a change map of the whole
table. Tick **＋ tables** as well and it carries on into the next table when one is done, cycling
holding → input → coil → discrete forever. (A wider **Count** sweeps faster; a lit **show** chip keeps
the sweep to just its matched registers — light **served** for an unattended walk, since the plain
no-chip view pages through the entire address space, dead registers included. A **Count** over 2000
asks for confirmation first — a full unfiltered pass of that many registers is slow.)

## What you see

- **Change heat** — a register that changes lights up; the more often it changes,
  the redder it stays (and it flashes brighter on each change), so fast-changing
  live measurements stand out from static config/identity registers at a glance.
  The `rate` column is the share of that register's own reads in which it changed.
- **Dead registers stay visible** — the plain view lists every known register, the refused ones
  included as greyed "not served" rows (write-only registers refuse every read, but they exist —
  and a device file's `bad_addresses:` show up the same way); the **refused** chip shows exactly
  those rows on their own. A refused address (Modbus illegal-data-address) is
  retried once, then — after a **second** refusal in a row — given up on: dropped from the read plan
  for good; it stays *listed*, just never re-probed — each dead row has a small **↻** button to probe
  exactly that one register again (**Clear all** re-arms them all at once). The **served** chip
  hides the dead ones instead — a **packed page** of only the registers the device answers, reading
  past the refused ones so the page always fills. **◀ / ▶** page through the matches; near an edge
  the window slides the other way to top up rather than leave a half-empty screen — except a **jump**
  (editing **Start** + **Apply range**) anchors the page firmly at Start and fills forward only, so
  it never slides back down into a region you set Start to skip. An *unreadable* stretch is never mistaken for an *absent*
  one: a bare timeout is retried a couple of times first (a slow device may just need another go,
  and a timed-out request can leave a late reply that trips the next read — the retry drains it),
  so paging past a fresh region on a slow gateway usually still advances on the first ▶. If it
  genuinely stays silent, the fill keeps the current page and its ◀ / ▶ anchors — paging stays
  enabled and simply retries once the device answers — instead of latching "at the end" and going
  dead.
- **Single-read downgrade** — when a block read fails, that block is bisected register by
  register to pin down the culprit(s), which is much slower; the header shows **`N single
  probes`** for the last scan/page. This kicks in two ways. A *refused* block (an illegal-data
  address exception) is always bisected. And some devices express an unsupported register by
  **not answering at all** (a timeout) rather than a refusal — so a block spanning it times out
  whole; when the device is answering its *other* registers (the link is proven up), such a
  block is bisected too, and the silent addresses are given up on so later reads skip them —
  otherwise that region would just say "no answer" forever. (A timeout while *nothing* is
  answering is treated as the whole link being briefly down: nothing is buried, it stays
  retryable.) Normal on first contact with a device that has holes — it settles as the dead
  list fills in (a couple of scans) — but if it never stops, the gateway may dislike block
  reads (lower **Per read**) or the serial side may just be very slow (a lower **Timeout**
  makes each dead probe cheaper). The probing stays **within the page you asked for**: the read
  is sized to **Count** (a Count of 3 reads 3, not a full **Per read** block), and the tiny
  look-ahead that decides whether ▶ is enabled peeks a single register without bisecting — so
  scanning a range that ends in a dead region never runs off bisecting hundreds of registers
  past it. While a bisection is running the header shows a live ⏳ status ("Isolating unreadable
  registers on holding — probing #124 (6 given up so far)…"), updated register by register, so a
  slow pass never looks like a frozen UI — it is polled from a lock-free endpoint, so it ticks
  *during* the blocking read, not after.
- **Remembered across tables** — every value is kept per `(table, address)`, so a value's
  read/change counts and history survive switching table or paging away and back (and rescanning
  then flags anything that moved while you were elsewhere). Switching tables keeps your view
  **position** too, falling back to the first page when the switched-to table serves nothing there.
- **Filter the view** — the **show** chips. Each chip is an additive toggle: a lit chip *adds* its
  register set to the page, and the view is the union of everything lit — any combination, one
  click each. **No chip lit is the plain view**: every known register, dead/refused rows included
  (write-only registers refuse reads but exist). The six chips: **served**, the registers the
  device answers; **refused**, the ones it refuses or that were given up on; **non-zero**, served
  registers with a non-zero value; **changed**, registers that moved at least once (once a sweep
  or two has run); **mapped**, everything the mapping — and any additive overlays — covers, probed
  or not, dead or alive; **x-ray**, every register that *any* table maps: a same-width sibling's
  mapping (holding ↔ input, coil ↔ discrete) appears muted as if it were mapped here — decoded
  against *this* table's registers — and as a tiny top-right corner tag when the register also has
  its own mapping; the non-compatible tables' mappings show on hover. An unmapped register showing
  a sibling mapping also gets a small **⧉ copy** button — one click copies that mapping onto this
  table at this address (renamed with a table suffix, since display names must stay unique). Handy
  for spotting — and fixing — entities written against the wrong table. Classic combinations are
  just chips: the old *mapped + changed* is `mapped` + `changed`; new ones like `mapped` +
  `non-zero` (your mapping plus anything alive it misses) come for free. **Count** sets how many
  rows a page shows in every view. Under the hood a page fill unions two sources: the scan chips
  *walk* the address space to discover matches (stopping where the device's map ends; the plain
  view pages the whole address space), while `mapped` / `x-ray` — and every chip's already-known
  matches — arrive as a *known set*, so a mapped register far off or refused, or a changed one you
  saw long ago beyond a dead stretch, is never missed. The **find** box narrows any view further:
  comma-separated terms, each a mapping-name part (`heat`), an exact address (`40`, `0x28`), or an
  address range (`10-20`) — a register shows if *any* term matches, on top of the lit chips. Name
  terms search this table's mappings (with `x-ray` lit: *every* table's), and the fill probes only
  the matching candidates — a fresh or imported session finds a far register without scanning up
  to it. And a **`=value`** term searches the registers' **last-known values**, in every
  reading: `=1000`, `=-87`, `=0xFFA9`, `=42.5` match the raw word (and its int16 view), the
  32/64-bit integer and float readings of *adjacent* registers — both word orders, matched at
  their start address — and mapped (or overlay) entities' numeric **decoded** values. Integers
  must match exactly; decimals match at the precision typed (`=42.5` covers 42.45..42.55,
  `=42.50` only 42.495..42.505) — "the display says 230.5 somewhere, find it" works even
  before anything is mapped. Value terms search what is *remembered* (current table only, no
  probing), so sweep the range once first; a register that changes later keeps its spot on the
  page until the search is re-applied. A fast way to find what matters in a big address space.
- **The Details tab** — click **any** of a register's data cells (address, value, hex, int16,
  Δ, rate) to open the side panel on **Details**. At the **top**, the "what type is this?" helper:
  the current value plus the uint/int/float/string interpretations of that register and the next few
  contiguous ones. **Below**, the last 50 *distinct* values it has taken — each with the Δ from the
  value before, the **Δt** to the *previous* change (a cadence like "every 60s" reads straight down
  the column; hover for how long ago it was — the summary line ends with the newest change's age in
  parentheses), the scan it appeared in, and a sparkline — hover a bar or a row and its partner
  lights up, linking *when* to *what* — so a steadily-climbing energy meter reads differently from
  a noisy measurement at a glance. The history's value column is **headed by its type**: when the
  register decodes *on its own* — a single-word mapping (its `uint16 ×0.1`-style type), or the
  Decode-as override (below) — the column shows the decoded value and the type says so; otherwise
  it shows the raw register value headed `uint16` (`bool` on bit tables). A multi-word entity can't
  decode from one register's history, so raw stays. And the **Decode as…** chip on the title line
  (accent-lit while active) sets ONE global *decode override* for the whole Details view: it opens
  the **Mapping** tab in a Details-view-only mode — the familiar editor with just the decode fields
  (type / swap / scale / offset / mask / enum map, single-word, validated by the real schema) —
  whose **Save**, **Unmap** and **Cancel** all return to Details. Saved, *every* word-table register
  you select decodes through it — replacing a mapped entity's decode, giving unmapped registers one,
  its type shown as the column header (bit tables read 0/1 and are left alone) — until **Unmap**
  drops it: try an interpretation across many registers while reverse-engineering without touching
  the mapping; the main table's decoded column stays the mapping's truth. Floats in the Details view show with strictly at most 3
  decimal places everywhere — a tiny magnitude reads 0 on screen, never a long tail or
  scientific notation — and **display-only**: the underlying data is never rounded, and
  wherever rounding changed the text, hovering the number shows the exact value. Hover any history cell for a quick
  recent-values peek, and walk registers with **↑ / ↓** — the tab follows the selection. Paired
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
  address — or a write-only register, which is fine). These show right in the plain view; the
  `mapped` / `x-ray` chips also list every mapped entity, dead addresses included (a multi-register
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

With the **additive** checkbox ticked, loading a further file *keeps* the current mapping and
stacks the new one underneath as a read-only **comparison overlay** — compare device models, or
spot registers a sibling model documents that your file doesn't. Overlays rank below the mapping
(and below earlier overlays — load order is priority order) and show like the x-ray does, but for
the current table: on a register nothing else maps, the overlay's entity fills the cell greyed,
tagged with the register's own address in plain text (it maps *here*, unlike a muted x-ray table
tag) and a **⧉ copy** that adopts it into your mapping; on an already-mapped register it joins
the tiny top-right corner tag, after any x-ray entries. With the `x-ray` chip lit each overlay
projects exactly like the mapping's own x-ray (sibling-table entities decoded against the current
table's registers), and the `mapped` / `x-ray` chips and name search cover overlay registers too —
so an overlay-only register is never missed. Overlays stay out of everything the mapping owns: the
generated file, the Manufacturer/Model stamp, and the dead-register seeding (`bad_addresses` of
another model may be alive here). They ride along in **Export**/**Import**; re-loading the same
file refreshes its overlay in place. Only **— none —** (or **Clear all**) drops them; a plain
(non-additive) load replaces mapping and overlays alike.

## Export · import · generate

- **Export / Import** — save the whole **project** to JSON and reload it later to pick up where you
  left off (or hand it to someone else). It captures every table's per-register stats — last value,
  read count, change count, and the value **history** — the editable **mapping**, any additive
  **overlays** and the Details-view **decode-as override**, the **connection**
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
