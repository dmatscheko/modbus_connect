# Modbus Scanner — live register scanner with a web UI

The device-file authoring tool. Point it at a Modbus TCP gateway and it walks the
device's registers in your browser: you see which ones answer, which change and
how fast, and what they might decode to; you map registers to entities by clicking
them; you test an existing device file against the live device; and you generate a
device file from what you mapped. It reuses the integration's own planner, schema
and codec, so what it shows is what the running integration would show.

## Run

```bash
.venv/bin/python support/modbus_scanner/scanner.py                              # set the host in the UI
.venv/bin/python support/modbus_scanner/scanner.py --host <gateway> --device-id 1
.venv/bin/python support/modbus_scanner/scanner.py --demo                       # simulated device, no hardware
```

Run it from a checkout of this repository with its virtualenv (it imports the
integration's modules). It opens <http://127.0.0.1:8765> (`--no-open` to skip
that, `--web-port` to move it). CLI flags — `--table`, `--start`, `--count`,
`--max-read`, `--port`, `--timeout`, `--retries`, `--device` — only seed the
initial values; everything is also set in the UI. The **Demo** device fakes a
device with static config registers, a fast and a slow counter, a sine, a
float32 ramp and a few refused addresses, so the whole UI can be tried without
hardware.

## Connect

Set host, port and device ID (or pick **Demo**) in the panel at the top and hit
**Connect**. Connecting sends one **probe read**: a gateway accepts a TCP
connection for *any* device ID, so only a read shows whether something answers
behind it. Any answer — data or a Modbus exception — proves a device is there;
silence, or a gateway *target failed to respond* exception, shows a ⚠ warning in
the header ("no answer from device ID 1 — check the Device ID") while staying
connected, since the device may just be offline. The warning self-heals on the
next real answer. During scanning the header stays honest the same way: an
operation where *nothing* answered says "no answer", one where some reads timed
out is a **slow** link (with a hint to raise Timeout), one that fully answers
clears the banner.

**Disconnect** always works, immediately: while a slow device is being scanned
or a big unreadable region bisected, a click cancels the in-flight read instead
of queueing behind it. Disconnecting and reconnecting keep everything gathered —
per-register stats and history, the mapping, the dead-register list — so you can
import a project and then connect to watch it live. **Clear all** is the one
deliberate reset: it drops the mapping and wipes every register's stats, history
and the dead list, so registers once given up on are probed again.

**Give up after** (`--retries`) is how many consecutive failed reads bury a
non-responding register on the dead list (default 2): raise it for a flaky link,
lower it to isolate truly dead registers in fewer scans. It is not a per-request
retry — transient timeouts are retried on their own.

## Scan and page

The register list shows in two side-by-side columns. **Start / Stop**, **Scan
once** and the interval sit in the header, so you can drive a scan with the
settings block hidden (**☰**). A browser refresh restores everything the server
knows: view, connection settings, the Manufacturer/Model stamp and the loaded
device file.

**◀ / ▶** page the range by exactly the number of registers shown, with a live
`start–end` readout between them; they are enabled purely by the address bounds.
**Start** always shows the first register on the page; editing it and hitting
**Apply range** *jumps* there and fills forward from that address — the fast way
to leap over a big unreadable stretch. **Count** is the rows per page in every
view; **Per read** is the block size (`max_register_read`).

Tick **auto-page** and each scan steps to the next page on its own, wrapping at
the end of the table; **＋ tables** carries on into the next table (holding →
input → coil → discrete) — leave it running and come back to a change map of the
whole device. A Count over 2000 asks for confirmation, as a full unfiltered pass
of that many registers is slow.

Every value is remembered per `(table, address)`, so read and change counts and
the value history survive paging away, switching tables, and disconnecting;
rescanning then flags whatever moved in the meantime.

## What you see

- **Change heat** — a register that changes lights up, the more often the redder
  (and it flashes on each change), so live measurements stand out from static
  config registers at a glance. `rate` is the share of that register's reads in
  which it changed.
- **Dead registers stay visible** — the plain view lists every known register,
  refused ones included as greyed "not served" rows: write-only registers refuse
  every read but exist, and a loaded file's `bad_addresses:` show the same way. A
  refused address is retried once and given up on after a second refusal in a row
  — kept in the list, never re-probed, with a **↻** button to probe exactly that
  register again.
- **Unreadable is not absent** — a bare timeout is retried a couple of times (a
  slow device may need another go, and a late reply from a timed-out request
  would otherwise trip the next read), and a stretch that stays silent keeps the
  current page and its paging anchors instead of latching "at the end".
- **Single-read downgrade** — when a block read fails, the block is bisected
  register by register to find the culprits, which is slower; the header shows
  **`N single probes`** and a live ⏳ status while it runs. A refused block is
  always bisected. A block that *times out* while the device answers its other
  registers is bisected too, because some devices express an unsupported register
  by not answering at all, and the silent addresses are given up on so later reads
  skip them (a timeout while nothing answers is a link outage: nothing is buried).
  This is normal on first contact and settles as the dead list fills in; if it
  never stops, the gateway may dislike block reads (lower **Per read**) or the
  serial side is very slow (a lower **Timeout** makes each dead probe cheaper).
  Probing stays within the page you asked for.

## Filter and find

The **show** chips are additive toggles: the view is the union of everything lit.
A chip filters what has **already been read or mapped** — it never reads ahead —
so its pages have exact bounds and paging through them is instant. **No chip lit
is the plain view**, which pages the whole address space and reads as it goes:
that is how you *discover* registers; the chips then filter what was found.

| chip | shows |
| --- | --- |
| **served** | registers already read that answered |
| **refused** | registers read and refused, or given up on as dead (write-only registers, a file's declared-dead hints) |
| **non-zero** | already-read registers with a non-zero value |
| **changed** | already-read registers whose value moved at least once |
| **mapped** | everything the mapping (and any overlays) covers, probed or not, dead or alive |
| **x-ray** | every register that *any* table maps: a same-width sibling's mapping (holding ↔ input, coil ↔ discrete) shows muted here, decoded against this table's registers, with a **⧉ copy** button to copy it onto this table |

The **find** box narrows any view further with comma-separated terms: a
mapping-name part (`heat`), an exact address (`40`, `0x28`), a range (`10-20`),
or a **`=value`** term that searches the last-known values in every reading —
raw word, int16, the 32/64-bit integer and float views of adjacent registers in
both word orders, and mapped entities' decoded values (`=1000`, `=0xFFA9`,
`=42.5`; decimals match at the precision typed). "The display says 230.5
somewhere, find it" works before anything is mapped. Value terms search what is
remembered, so sweep the range once first.

## Details

Click any of a register's data cells (address, value, hex, int16, Δ, rate) to
open the side panel on **Details**; **↑ / ↓** move the selection and the panel
follows. At the top, the "what type is this?" helper: the current value and the
uint/int/float/string readings of this register and the next few. Below, the last
50 distinct values with the Δ from the previous value, the Δt to the previous
change (a cadence like "every 60 s" reads straight down the column), the scan it
appeared in, and a sparkline.

The history's value column is headed by its type: when the register decodes on
its own — a single-word mapping, or the **Decode as…** override — it shows the
decoded value; otherwise the raw word. **Decode as…** sets one global decode
override for the Details view (type, swap, scale, offset, mask, enum map,
validated by the real schema): every word-table register you select then decodes
through it, without touching the mapping — for trying an interpretation across
many registers while reverse-engineering. Floats show with at most three
decimals; hover for the exact value.

## Map registers

Two columns are always shown: **mapped as** (the entity mapped there; continuation
registers of a multi-word entity show `↑ name`; unmapped registers a faint
**＋ map**) and **decoded** (the value that entity decodes to through the
integration's own codec). Click either to open the **Mapping** tab. The editor
exposes what the integration supports — name, platform, type and swap, scale,
offset, `sum_scale`, mask, enum map, flags, unit, device and state class,
precision, category, icon, min/max/step, on/off values, `write_value` — plus an
**advanced** YAML block for any other device-file key (`groups`, `scan_interval`,
write tuning, extra `ha:` fields). **Save** validates the mapping with the
integration's real schema; a bad combination is refused inline and the previous
mapping kept. Mappings span all four tables.

Two mistakes stand out in the plain view: a register the device **serves but
nothing maps** gets an amber `unmapped` badge, and a register a mapping points at
but the device **refuses** a red `refused ✕` badge (a wrong address — or a
write-only register, which is fine).

### Load a device file

Pick a bundled file from the **Load a device file** dropdown, **Upload…** your
own, or pass `--device <path-or-basename>` at startup, to load it as the editable
mapping: test it against the live device, then tweak and regenerate. The **fit
range** buttons jump the scan to exactly what it maps on each table, and its
`bad_addresses:` are applied up front. **— none —** drops the mapping but keeps
stats, history and the dead list. After an **Import**, the dropdown gains an
`imported · <manufacturer> <model>` entry so you can switch away and back without
losing the edits.

With **additive** ticked, loading a further file keeps the current mapping and
stacks the new one underneath as a read-only **comparison overlay** — to compare
device models, or to spot registers a sibling model documents that your file
misses. Overlays rank below the mapping and below earlier overlays, show like the
x-ray does (greyed, with a **⧉ copy** button that adopts an entry into your
mapping), and stay out of everything the mapping owns: the generated file, the
Manufacturer/Model stamp, and the dead-register seeding. They ride along in
Export/Import.

## Export, import, generate

- **Export / Import** save and reload the whole **project** as JSON: every
  table's per-register stats and value history, the mapping, overlays, the decode
  override, the connection settings, the Count / Per read tuning, and the
  Manufacturer / Model stamp. Deliberately not saved: the table, position, filter
  and which bundled file was picked, so loading a project does not yank you off
  what you are looking at.
- **Generate device file** (the **Generate** tab) — set manufacturer and model
  and get a valid device file: every entity you mapped, a bare sensor for each
  *ticked* served register that is still unmapped (`state_class: measurement` on
  the ones that moved), and a `bad_addresses:` hint reduced to the few entries
  the integration's planner can act on — one per gap between mapped registers —
  so the file stays small while producing the same reads. Refine the rest by hand
  with the [device-file reference](../../docs/device_files.md).

`support/modbus_cli.py` is the terminal counterpart for one-off probes, reads
and writes; it imports nothing from the repository, so it can be copied to any
machine.
