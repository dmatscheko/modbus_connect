#!/usr/bin/env python3
"""Live Modbus register scanner with a small web UI — for device-file authors.

Point it at a gateway, pick a table + start address, and it rescans on an interval and shows a
packed page of registers: every known one for the plain view — dead/refused registers included as
greyed rows (write-only registers refuse reads but exist) — or a filtered subset (``served`` is the
answers-only view; mapped / non-zero / changed / x-ray narrow further). Registers that *change*
light up (yellow → red the more/faster they change), making the map legible at a glance:
fast-changing = live measurements, static = config/identity. Values are remembered per
(table, address), so their read/change counts and history survive switching table or paging away
and back.

From there you build a device file interactively: click an unmapped register to map it
(name, platform, type, scale, unit, …), click a mapped one to edit or unmap it. Every
mapping is validated by the integration's own ``schema`` the moment you make it and
decoded by its ``codec`` (so the overlay is exactly what the running integration would
show), and every mapping is included when you generate the device-file skeleton. You can
also load an existing device file to test/adjust it — it becomes the editable mapping —
and, with the UI's *additive* checkbox, stack further files under it as read-only
comparison overlays (grey in the UI), e.g. a sibling model's file to spot what it
documents that yours doesn't.

Unlike the standalone ``support/modbus_cli.py`` (which imports nothing, to stay copyable),
this tool **reuses the integration's own code** so its verdicts match runtime exactly:
``planner.plan_blocks`` (efficient, hole-skipping reads — the coordinator's block planning),
``models`` (the table/type vocabulary), and ``schema`` + ``codec`` (to parse the mapping and
decode its registers exactly as the running integration would).

Run from the repo virtualenv (needs pymodbus; the integration modules are imported):

    .venv/bin/python support/modbus_scanner/scanner.py            # set the host in the UI
    .venv/bin/python support/modbus_scanner/scanner.py --host my-gateway --device-id 1
    .venv/bin/python support/modbus_scanner/scanner.py --demo     # simulated device, no hardware

then open http://127.0.0.1:8765 and set the connection (host/port/id, or Demo) in the UI —
``--host`` / ``--demo`` are just shortcuts. ``--demo`` fakes a device (static, counters, a
sine, a float ramp, and a few refused addresses) so you can see everything with no gateway.
"""
from __future__ import annotations

import argparse
import bisect
import contextlib
import copy
import json
import math
import re
import struct
import sys
import threading
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml

# Reuse the integration's own code (run from the repo venv) — planning + vocabulary,
# and, to overlay a device file on the scan, its parser + codec so the decoded values
# and verdicts match runtime exactly.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from custom_components.modbus_connect import codec
from custom_components.modbus_connect.loader import _device_label
from custom_components.modbus_connect.models import (
    BIT_TABLES,
    PROTOCOL_MAX_BITS,
    PROTOCOL_MAX_REGISTERS,
    TABLES,
    DeviceDef,
    EntityDef,
    Span,
    derive_name,
)
from custom_components.modbus_connect.planner import plan_blocks
from custom_components.modbus_connect.schema import DeviceSchemaError, parse_device

HERE = Path(__file__).resolve().parent
CONFIG_DIR = Path(__file__).resolve().parents[2] / "custom_components/modbus_connect/device_configs"
_ILLEGAL_DATA_ADDRESS = 2  # Modbus exception code: "the device does not serve this address"
# Filling a page scans forward/back until it has enough matches. Stop a direction after this
# many consecutive unmatched addresses (the device's register map ended there — or, offline,
# the remembered cells did), and never read more than this many addresses for one page fill.
_FILTER_DEAD_RUN = 128
_FILTER_FILL_CAP = 4096

# The view filters: the scanned views (none / served / non-zero / changed) walk the table for
# matches; the set-based views window over a known membership set (see Scanner._filter_members).
# "none" is the plain view: every known register, dead/refused ones included (write-only
# registers refuse reads but exist); "served" hides the dead ones — a packed page of answers.
_SET_FILTERS = ("mapped", "mappedchanged", "xray", "xraychanged")
_FILTERS = ("none", "served", "nonzero", "changed", *_SET_FILTERS)
_XRAY_FILTERS = ("xray", "xraychanged")
_CHANGED_UNIONS = ("mappedchanged", "xraychanged")  # the set views that add every moved register

# The find box: comma-separated terms, each an exact address ('40' / '0x28'), an address
# range ('10-20', hex ok), or a case-insensitive mapping-name/key substring. A register
# matches when ANY term does; the whole search ANDs with the selected view filter.
_RANGE_RE = re.compile(r"(0[xX][0-9a-fA-F]+|\d+)\s*-\s*(0[xX][0-9a-fA-F]+|\d+)")


def _parse_search(text: str) -> list[tuple[Any, ...]]:
    """The find box, parsed into match terms (see _RANGE_RE comment)."""
    terms: list[tuple[Any, ...]] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        m = _RANGE_RE.fullmatch(part)
        if m:
            lo, hi = int(m.group(1), 0), int(m.group(2), 0)
            terms.append(("range", min(lo, hi), max(lo, hi)))
            continue
        try:
            terms.append(("addr", int(part, 0)))
        except ValueError:
            terms.append(("name", part.casefold()))
    return terms
# The x-ray views project mappings between the same-width tables: word <-> word, bit <-> bit.
_SIBLING = {"holding": "input", "input": "holding", "coil": "discrete", "discrete": "coil"}
# A register the device refuses (illegal-data-address) is only given up on — dropped from the
# read plan (a reconnect keeps that; Clear all or the row's ↻ retry re-arm it) — after this many
# *consecutive* "not served" answers, so a single spurious refusal doesn't kill a register
# (a served read in between resets the count).
_NOT_SERVED_LIMIT = 2
# Per register we keep a short history of its *distinct-from-previous* values (with the scan
# index and wall-clock time each was first seen), so after a long unattended sweep the UI can
# show how a value moved. Capped per cell; a compact tail rides along in each row for the tooltip.
HISTORY_MAX = 50
HISTORY_SPARK = 20


# --- read backends ------------------------------------------------------------
# A reader answers one block read: (values, error, illegal). ``values`` is None on
# failure; ``illegal`` is True only when the device explicitly refused the address
# (vs. a timeout), which is what marks a register genuinely "not served".
@dataclass(frozen=True)
class ReadResult:
    values: list[int] | None
    error: str | None = None
    illegal: bool = False


Reader = Callable[[str, int, int], ReadResult]


def pymodbus_reader(
    host: str, port: int, device_id: int, timeout: float, retries: int
) -> tuple[Reader, Callable[[], bool], Callable[[], None]]:
    """A synchronous pymodbus TCP reader plus connect()/close()."""
    from pymodbus.client import ModbusTcpClient
    from pymodbus.exceptions import ModbusException
    from pymodbus.pdu import ExceptionResponse

    client = ModbusTcpClient(host, port=port, timeout=timeout, retries=retries)
    funcs = {
        "holding": client.read_holding_registers,
        "input": client.read_input_registers,
        "coil": client.read_coils,
        "discrete": client.read_discrete_inputs,
    }

    def read(table: str, address: int, count: int) -> ReadResult:
        try:
            rr = funcs[table](address=address, count=count, device_id=device_id)
        except ModbusException as exc:
            return ReadResult(None, str(exc))
        if rr.isError():
            code = rr.exception_code if isinstance(rr, ExceptionResponse) else None
            return ReadResult(None, f"exception {code}" if code else str(rr),
                              illegal=code == _ILLEGAL_DATA_ADDRESS)
        raw = rr.bits if table in BIT_TABLES else rr.registers
        return ReadResult([int(v) for v in raw[:count]])

    return read, (lambda: bool(client.connect())), client.close


def demo_reader() -> Reader:
    """A fake device so the UI works with no hardware: static config, a fast and a
    slow counter, a sine, a float32 ramp, and a couple of refused addresses."""
    t0 = time.monotonic()

    def one(address: int) -> ReadResult:
        t = time.monotonic() - t0
        if address in (8, 9) or address >= 64:
            return ReadResult(None, "exception 2", illegal=True)  # not served (map ends at 63)
        if address < 4:
            return ReadResult([0x0100 + address])                 # static config
        if address == 4:
            return ReadResult([int(t * 10) & 0xFFFF])             # fast counter
        if address == 5:
            return ReadResult([int(t / 5) & 0xFFFF])             # slow counter
        if address == 6:
            return ReadResult([2000 + int(1000 * math.sin(t))])   # sine (changes often)
        if address in (10, 11):  # a big-endian float32 ramp across two registers
            raw = struct.pack(">f", 20.0 + t / 30)
            hi, lo = struct.unpack(">HH", raw)
            return ReadResult([hi if address == 10 else lo])
        if address % 10 == 0:
            return ReadResult([address])                          # a scattered non-zero here and there
        return ReadResult([0])                                    # quiet zeros

    def read(table: str, address: int, count: int) -> ReadResult:
        values: list[int] = []
        for a in range(address, address + count):
            r = one(a)
            if r.values is None:
                return r  # whole block fails if any address is refused (real devices do this)
            values.extend(r.values)
        return ReadResult(values)

    return read


# --- scan state ---------------------------------------------------------------
@dataclass
class Cell:
    address: int
    value: int | None = None
    changes: int = 0
    reads: int = 0          # times a value was read (rate denominator; scans skip other tables)
    last_changed: int = -1  # scan index at the last value change (-1 = never)
    error: str | None = None
    illegal: bool = False
    # the last HISTORY_MAX distinct-from-previous values: {"value", "scan", "t"} (t = epoch secs)
    history: list[dict[str, Any]] = field(default_factory=list)


def _index_entities(device: DeviceDef) -> tuple[dict[tuple[str, int], EntityDef],
                                                dict[tuple[str, int], EntityDef]]:
    """Index a parsed device's entities: by their first (table, address), and by every
    (table, address) any of them occupies — the mapping's and each overlay's lookups."""
    starts: dict[tuple[str, int], EntityDef] = {}
    covered: dict[tuple[str, int], EntityDef] = {}
    for e in device.entities:
        starts[(e.table, e.address)] = e
        for a in range(e.span.start, e.span.end):
            covered[(e.table, a)] = e
    return starts, covered


@dataclass
class Overlay:
    """An additively loaded device file: a read-only comparison layer *under* the editable
    mapping (and under earlier overlays — load order is priority order). Its entities fill
    only where nothing higher-priority maps (the UI greys them), so loading a sibling
    model's file shows what *it* documents without touching your work."""
    name: str
    doc: dict[str, Any]
    device: DeviceDef
    starts: dict[tuple[str, int], EntityDef]
    covered: dict[tuple[str, int], EntityDef]


def _clamp_range(start: int, count: int) -> tuple[int, int]:
    """Clamp a [start, count) range into the Modbus 16-bit address space (registers
    0..65535), so start+count never runs past the last address."""
    start = max(0, min(0xFFFF, int(start)))
    return start, max(1, min(0x10000 - start, int(count)))


def _clamp_max_read(table: str, max_read: int) -> int:
    """Clamp per-read size to the protocol's per-request limit for the table — 125
    registers for word tables, 2000 bits for coil/discrete."""
    cap = PROTOCOL_MAX_BITS if table in BIT_TABLES else PROTOCOL_MAX_REGISTERS
    return max(1, min(cap, int(max_read)))


class Scanner:
    """Holds the range config and the per-(table, address) stats, and does one scan
    pass at a time. Reads are planned with the integration's ``plan_blocks`` over the
    addresses not yet known-refused, so rescans skip dead registers automatically.
    Cells are kept across table/range changes, so the memory spans the whole device.

    An editable mapping (a device-file document) can be built up by mapping registers
    or seeded by loading a file; it is parsed by the integration's schema for the live
    overlay and dumped when generating the device-file skeleton."""

    def __init__(self, read: Reader | None = None, *, table: str, start: int,
                 count: int, max_read: int) -> None:
        # Connection: set up front via --host/--demo, or live in the UI (POST /api/connect).
        self._read = read
        self._close: Callable[[], None] | None = None
        self.connected = read is not None
        self.conn_error: str | None = None
        self.connection: dict[str, Any] = {"mode": "", "host": "", "port": 502, "device_id": 1,
                                           "timeout": 2.0, "retries": 0}
        self.table = table
        self.start, self.count = _clamp_range(start, count)
        self.max_read = _clamp_max_read(table, max_read)
        self.filter = "none"   # registers a page shows — one of _FILTERS ("none" = every known register)
        self.search = ""       # the find box: narrows any view further (see _parse_search)
        self._search_terms: list[tuple[Any, ...]] = []
        self.page_size = self.count   # rows per page (the UI keeps this equal to Count, in every view)
        self.cells: dict[tuple[str, int], Cell] = {}  # (table, address) -> stats, across all tables
        # The dead-register list: (table, address) given up on -> always-on planner holes. One
        # concept across the layers: rows carry it as "dead", cells/exports as the error string
        # "not served" (a persistence contract — load_state rebuilds this set from it, so never
        # rename that string), and generated device files as their bad_addresses hint.
        self._bad: set[tuple[str, int]] = set()
        self._misses: dict[tuple[str, int], int] = {}  # consecutive "not served" answers, until _bad
        self.scan_index = 0
        self.last_error: str | None = None  # a connection-level failure, shown in the UI
        # The editable mapping: a device-file document (or None). Parsed into ``device``
        # + the (table, address) indexes below, and dumped when generating a skeleton.
        self.map_doc: dict[str, Any] | None = None
        self.device: DeviceDef | None = None
        self.device_name: str = ""
        # The manufacturer/model stamped on a generated file: seeded from a loaded device
        # file, editable live in the UI, part of the project (export/import) — the server
        # keeps it so a browser refresh cannot lose it.
        self.meta: dict[str, str] = {"manufacturer": "", "model": ""}
        # The session's memory of an imported project's mapping (+ its stamp): the dropdown
        # shows it as an 'imported · <name>' entry, so you can switch to a bundled file (or
        # none) and back without losing it. Kept in sync with edits while it is the active
        # mapping; only Clear all forgets it.
        self.imported: dict[str, Any] | None = None
        # Additively loaded device files (the UI's "additive" checkbox): read-only comparison
        # overlays under the editable mapping, in load order (earlier = higher priority).
        # A plain (non-additive) load replaces them; — none — / Clear all drop them.
        self.additional: list[Overlay] = []
        self._starts: dict[tuple[str, int], EntityDef] = {}   # entity's first address
        self._covered: dict[tuple[str, int], EntityDef] = {}  # every address any entity occupies
        # The current filtered page: its matched addresses, and where paging continues in
        # each direction (None once that direction is exhausted at the table/map edge).
        self._page_addrs: list[int] = []
        self._page_next_anchor: int | None = None
        self._page_prev_anchor: int | None = None

    def connect(self, *, mode: str = "tcp", host: str = "", port: int = 502, device_id: int = 1,
                timeout: float = 2.0, retries: int = 0) -> None:
        """(Re)open the connection from UI/CLI settings. Everything the session has gathered —
        every table's per-register stats and value history, the mapping, and the given-up-on
        (dead) register list — is **kept**, so importing a project and then connecting to watch
        it live never costs you your work; only **Clear all** (``clear_all``) wipes that.
        ``demo`` uses the simulated device; ``tcp`` connects to a gateway. Connection errors are
        stored (``conn_error``) and surfaced in the UI, not raised."""
        self._teardown()
        self.connection = {"mode": mode, "host": host, "port": int(port),
                           "device_id": int(device_id), "timeout": float(timeout), "retries": int(retries)}
        if mode == "demo":
            self._read, self.connected, self.conn_error = demo_reader(), True, None
        elif not host:
            self.connected, self.conn_error = False, "host is required"
        else:
            read, do_connect, close = pymodbus_reader(
                host, int(port), int(device_id), float(timeout), int(retries))
            if do_connect():
                self._read, self._close, self.connected, self.conn_error = read, close, True, None
            else:
                self.connected, self.conn_error = False, f"cannot connect to {host}:{port}"
        self.last_error = None
        self._clear_page()  # refill the view from the current inputs; the stats behind it survive

    def disconnect(self) -> None:
        """Deliberately drop the connection (the Connect button's other half). Everything
        gathered stays — stats, history, mapping, dead list, and the settings for the next
        Connect — and the view keeps showing the remembered values, just frozen."""
        self._teardown()
        self.conn_error = None  # a chosen state, not a failure
        self.last_error = None

    def _clear_page(self) -> None:
        self._page_addrs, self._page_next_anchor, self._page_prev_anchor = [], None, None

    def _teardown(self) -> None:
        if self._close is not None:
            with contextlib.suppress(Exception):  # best-effort close of the old connection
                self._close()
        self._read, self._close, self.connected = None, None, False

    def reconfigure(self, *, table: str, start: int, count: int, max_read: int,
                    filter_mode: str = "none", page_size: int | None = None,
                    search: str | None = None) -> None:
        # Keep the per-(table, address) memory so switching table/range and coming back
        # still shows the last values (and marks what changed meanwhile). Clamp the range
        # into the address space so an oversized request can't drive scans past the last register.
        start, count = _clamp_range(start, count)
        new_filter = filter_mode if filter_mode in _FILTERS else "none"
        new_search = self.search if search is None else search  # None = keep the current search
        if table != self.table or new_filter != self.filter or new_search != self.search:
            self._clear_page()  # a table/filter/search switch fills a fresh page
        self.table, self.start, self.count, self.max_read = (
            table, start, count, _clamp_max_read(table, max_read))
        self.filter = new_filter
        if new_search != self.search:
            self.search, self._search_terms = new_search, _parse_search(new_search)
        if page_size:
            self.page_size = max(1, int(page_size))

    def scan(self) -> None:
        """One tick: re-read the current page's registers (membership unchanged) so a live scan
        keeps their values fresh; the first tick fills the page. Every view is a packed page —
        every known register for the plain view (dead ones included), or a filtered subset (served /
        mapped / non-zero / changed / their unions / the x-ray projection of every table's mappings)."""
        if not self.connected or self._read is None:
            self.last_error = "not connected"
            return
        self.scan_index += 1
        if self._page_addrs:
            self.refresh_page()
        else:
            self._fill_page(forward=True, anchor=self.start)  # establish the page on the first tick

    def _read_range(self, start: int, count: int) -> str | None:
        """Read & record [start, start+count) on the current table, planned so already-refused
        addresses (in _bad) are skipped. Returns an error string on a persistent no-answer."""
        addrs = [a for a in range(start, start + count) if (self.table, a) not in self._bad]
        return self._read_spans({Span(self.table, a, 1) for a in addrs})

    def _read_spans(self, spans: set[Span]) -> str | None:
        """Read & record a set of single-address spans, planned into efficient blocks; a
        block the device refuses is bisected to the individual refused address(es)."""
        read = self._read
        if read is None:
            return None
        silent = 0
        for block in plan_blocks(spans, max_read=self.max_read, holes=self._bad):
            result = read(self.table, block.start, block.count)
            if result.values is not None:
                for i, addr in enumerate(range(block.start, block.end)):
                    self._record(self.table, addr, value=result.values[i])
                silent = 0
            elif result.illegal:
                self._bisect(block)  # device refused the block: find which address(es)
            else:
                silent += 1  # a timeout/transport error: the device (or gateway) is quiet
                if silent >= 3:
                    return result.error or "no answer"
        return None

    def refresh_page(self) -> None:
        """Re-read the registers of the current filtered page (its membership unchanged),
        so a live scan keeps their values fresh without reshuffling what's shown."""
        self.last_error = None
        spans: set[Span] = set()
        for addr in self._page_addrs:
            spans |= {Span(self.table, a, 1) for a in self._row_read_addrs(addr)
                      if (self.table, a) not in self._bad}
        if spans:
            self.last_error = self._read_spans(spans)

    def _bisect(self, block: Span) -> None:
        """Read each address of a refused block alone to pin down the culprit(s). An address is
        only given up on (added to _bad, skipped from now on) after _NOT_SERVED_LIMIT refusals in
        a row; a single "not served" is shown but retried next scan."""
        for addr in range(block.start, block.end):
            r = self._read(self.table, addr, 1)
            key = (self.table, addr)
            if r.values is not None:
                self._record(self.table, addr, value=r.values[0])
            elif r.illegal:
                self._misses[key] = self._misses.get(key, 0) + 1
                if self._misses[key] >= _NOT_SERVED_LIMIT:
                    self._bad.add(key)
                self._record(self.table, addr, error="not served", illegal=True)
            else:
                self._misses.pop(key, None)  # a no-answer isn't a refusal -> breaks the streak
                self._record(self.table, addr, error=r.error or "no answer")

    def retry_address(self, table: str, address: int) -> None:
        """Probe one given-up-on register again — the per-register escape hatch from the dead
        list (Clear all is the global one; useful when a register was dead only temporarily).
        Answers -> it rejoins the served set; still refused -> straight back on the dead list
        (this was the one explicit retry); a no-answer just shows, so later scans re-probe."""
        key = (table, address)
        self._bad.discard(key)
        self._misses.pop(key, None)
        if self._read is None or table != self.table:
            return  # offline (or not the shown table): just un-dead it for the next scans
        r = self._read(table, address, 1)
        if r.values is not None:
            self._record(table, address, value=r.values[0])
        elif r.illegal:
            self._bad.add(key)
            self._record(table, address, error="not served", illegal=True)
        else:
            self._record(table, address, error=r.error or "no answer")

    def _record(self, table: str, address: int, *, value: int | None = None,
                error: str | None = None, illegal: bool = False) -> None:
        cell = self.cells.setdefault((table, address), Cell(address))
        cell.error = error
        cell.illegal = illegal
        if value is not None:
            cell.reads += 1
            self._misses.pop((table, address), None)  # a served read breaks the not-served streak
            changed = cell.value is not None and value != cell.value
            if changed:
                cell.changes += 1
                cell.last_changed = self.scan_index
            if cell.value is None or changed:  # first read or a new distinct value -> history
                cell.history.append({"value": value, "scan": self.scan_index, "t": time.time()})
                del cell.history[:-HISTORY_MAX]  # keep only the most recent HISTORY_MAX
            cell.value = value

    # --- paging --------------------------------------------------------------
    def page(self, *, forward: bool, anchor: int) -> None:
        """Fill a page from ``anchor`` in one direction, scanning as far as needed to collect
        page_size matches (or reach the table/map edge). Finding nothing that way keeps the current
        page and just marks that direction exhausted (no empty page). Offline it still fills from the
        remembered cells (with no fresh reads), so an imported project can be reviewed unconnected."""
        if self.connected and self._read is not None:
            self.scan_index += 1
        else:
            self.last_error = "not connected"
        self._fill_page(forward, anchor)

    def _fill_page(self, forward: bool, anchor: int) -> None:
        self.last_error = None
        matched, nxt, prv = self._collect_page(forward, anchor)
        if matched:
            self._page_addrs, self._page_next_anchor, self._page_prev_anchor = matched, nxt, prv
        elif forward:
            self._page_next_anchor = None
        else:
            self._page_prev_anchor = None

    def open_page(self) -> None:
        """Fill the page from the current start, falling back to the first page if nothing shows
        there (nothing served/matched at or past start). Used on every view load (/api/config) and
        when restoring a view (import): a table switch or a saved scroll position must never strand
        the view in empty space with no way to page back."""
        self._clear_page()
        self.page(forward=True, anchor=self.start)
        if not self._page_addrs and self.start > 0:
            self.start = 0
            self.page(forward=True, anchor=0)

    def _scan_run(self, forward: bool, anchor: int, limit: int) -> list[int]:
        """Scan in one direction from ``anchor``, returning up to ``limit`` matching addresses,
        sorted ascending: every *known* register for the plain view (dead/refused ones included —
        write-only registers refuse reads but exist), or the served / non-zero / changed subset.
        Stops at the table edge, a long unmatched run (the map ended), or the fill cap."""
        matched: list[int] = []
        pos, dead, scanned = anchor, 0, 0
        while len(matched) < limit and scanned < _FILTER_FILL_CAP:
            if (forward and pos > 0xFFFF) or (not forward and pos < 0):
                break
            count = min(self.max_read, 0x10000 - pos) if forward else min(self.max_read, pos + 1)
            start = pos if forward else pos - count + 1
            if self._read_range(start, count):
                break  # device stopped answering — return what we have
            scanned += count
            block = range(start, start + count) if forward else reversed(range(start, start + count))
            for a in block:
                cell = self.cells.get((self.table, a))
                # the plain view lists everything known: a recorded cell (value or refusal) or a
                # seeded known-dead address; the filtered views list served registers only
                known = cell is not None or (self.table, a) in self._bad
                served = cell is not None and cell.error is None
                if not (known if self.filter == "none" else served):
                    dead += 1
                    continue
                dead = 0
                if self.filter == "nonzero" and cell.value == 0:  # non-zero view also hides served zeros
                    continue
                if self.filter == "changed" and not cell.changes:  # changed view: only registers that moved
                    continue
                matched.append(a)
                if len(matched) >= limit:
                    break
            pos = start + count if forward else start - 1
            if dead >= _FILTER_DEAD_RUN:  # a long refused run — the device's map ended here
                break
        matched.sort()
        return matched

    def _search_candidates(self) -> list[int]:
        """Every address the active search could match — computable outright, no scanning:
        address and range terms name their addresses; name terms contribute the covered
        addresses (every table's in the x-ray views, else this table's) whose entity
        name/key contains the term. The search fill probes only these candidates, so a
        fresh session finds a far register as fast as an already-scanned one."""
        out: set[int] = set()
        tables = TABLES if self.filter in _XRAY_FILTERS else (self.table,)
        indexes = [self._covered] + [ov.covered for ov in self.additional]
        for term in self._search_terms:
            if term[0] == "addr":
                if 0 <= term[1] <= 0xFFFF:
                    out.add(term[1])
            elif term[0] == "range":
                out.update(range(max(0, term[1]), min(term[2], 0xFFFF) + 1))
            else:
                for index in indexes:
                    for (t, a), defn in index.items():
                        if t in tables and (term[1] in (defn.ha.get("name") or "").casefold()
                                            or term[1] in defn.key.casefold()):
                            out.add(a)
        return sorted(out)

    def _row_shows(self, addr: int) -> bool:
        """Whether the current view lists this (already probed) register — the predicate
        _scan_run applies while walking, restated for the candidate-driven search fill.
        The set views vetted membership already, so everything passes there. The plain
        view also counts a *mapped* register as known even with no cell behind it (an
        imported project may carry the mapping but not that register's reads; offline,
        a name match must still show its row)."""
        if self.filter in _SET_FILTERS:
            return True
        cell = self.cells.get((self.table, addr))
        if self.filter == "none":
            return (cell is not None or (self.table, addr) in self._bad
                    or (self.table, addr) in self._covered
                    or any((self.table, addr) in ov.covered for ov in self.additional))
        if cell is None or cell.error is not None:
            return False
        if self.filter == "nonzero":
            return cell.value != 0
        if self.filter == "changed":
            return bool(cell.changes)
        return True  # served

    def _search_run(self, cands: list[int], forward: bool, anchor: int, limit: int) -> list[int]:
        """Probe search candidates from ``anchor`` in one direction and keep those the
        view shows. Reads go in chunks (the planner merges them into blocks); a direction
        ends at ``limit`` keeps, the candidates' end, or a long run of failing candidates
        (mirroring the scan views' dead-run stop)."""
        idx = bisect.bisect_left(cands, anchor) if forward else bisect.bisect_right(cands, anchor) - 1
        step = 1 if forward else -1
        kept: list[int] = []
        misses = 0
        while 0 <= idx < len(cands) and len(kept) < limit and misses < _FILTER_DEAD_RUN:
            chunk: list[int] = []
            while 0 <= idx < len(cands) and len(chunk) < 128:
                chunk.append(cands[idx])
                idx += step
            addrs = {x for a in chunk for x in self._row_read_addrs(a)
                     if (self.table, x) not in self._bad}
            if addrs and self._read is not None:
                self._read_spans({Span(self.table, x, 1) for x in addrs})
            for a in chunk:
                if self._row_shows(a):
                    kept.append(a)
                    misses = 0
                    if len(kept) >= limit:
                        break
                else:
                    misses += 1
                    if misses >= _FILTER_DEAD_RUN:
                        break
        kept.sort()
        return kept

    def _collect_search_page(self, forward: bool, anchor: int,
                             want: int) -> tuple[list[int], int | None, int | None]:
        """The page fill while a search is active: window over the candidate set instead
        of walking the address space (set views intersect their membership first), then
        top up the other way when short at an edge, like the scanned fills do."""
        cands = self._search_candidates()
        if self.filter in _SET_FILTERS:
            members = self._filter_members()
            cands = [a for a in cands if a in members]
        if not cands:
            return [], None, None
        page = self._search_run(cands, forward, anchor, want)
        if 0 < len(page) < want:  # short at an edge: slide the window the other way to fill
            if forward:
                page = sorted(self._search_run(cands, False, page[0] - 1, want - len(page)) + page)
            else:
                page = sorted(page + self._search_run(cands, True, page[-1] + 1, want - len(page)))
        if not page:
            return [], None, None
        nxt = next((a for a in cands if a > page[-1]), None)
        prv = next((a for a in reversed(cands) if a < page[0]), None)
        return page, nxt, prv

    def _filter_members(self) -> set[int]:
        """Addresses the set-based views select on the current table: the mapped registers
        (every address any entity occupies, additive overlays included) — for the x-ray
        views *every* table's mapped addresses, projected onto this table — plus, for the
        *+ changed* variants, every served register that has moved at least once. A
        set-based view windows over this *known* set, so (unlike the scanned plain /
        non-zero / changed views) it never misses a mapped register that sits far away or
        that the device refuses."""
        if self.filter in _XRAY_FILTERS:  # a mapping in any table puts its address on this view
            members = {a for (_t, a) in self._covered}
            members.update(a for ov in self.additional for (_t, a) in ov.covered)
        else:
            members = {a for (t, a) in self._covered if t == self.table}
            members.update(a for ov in self.additional for (t, a) in ov.covered if t == self.table)
        if self.filter in _CHANGED_UNIONS:
            members |= {a for (t, a), cell in self.cells.items()
                        if t == self.table and cell.error is None and cell.changes}
        return members

    def _row_read_addrs(self, addr: int) -> set[int]:
        """The current-table addresses to read for one page row. In the set-based views a
        locally mapped register expands to its entity's whole span (so split entities still
        decode); the x-ray views also expand a sibling-table entity's span, since that entity
        is decoded against *this* table's registers — both for the editable mapping and for
        every additive overlay. Everything else is just the address."""
        out = {addr}
        if self.filter in _SET_FILTERS:
            xray = self.filter in _XRAY_FILTERS
            indexes = [self._covered] + [ov.covered for ov in self.additional]
            for index in indexes:
                defns = [index.get((self.table, addr))]
                if xray:
                    defns.append(index.get((_SIBLING[self.table], addr)))
                for defn in defns:
                    if defn is not None:
                        out.update(range(defn.span.start, defn.span.end))
        return out

    def _collect_page(self, forward: bool, anchor: int) -> tuple[list[int], int | None, int | None]:
        """Collect a full window of page_size registers around ``anchor`` and return (page,
        next_anchor, prev_anchor). Every page is filled to page_size when that many registers
        exist: it scans the paging direction, and if it comes up short at an edge it slides the
        window the other way to top it up — so paging never leaves a half-empty screen. The
        anchors are the next / previous register just beyond the page (None at the true ends, so
        ▶ / ◀ disable there — no paging past the registers that exist)."""
        want = max(1, self.page_size)
        if self._search_terms:  # the find box ANDs with the view filter (candidate-driven)
            return self._collect_search_page(forward, anchor, want)
        if self.filter in _SET_FILTERS:
            # window of `want` addresses over the filter's known set (see _filter_members),
            # sliding to fill
            members = sorted(self._filter_members())
            if not members:
                return [], None, None
            if forward:
                page = [a for a in members if a >= anchor][:want]
                if len(page) < want:
                    page = members[-want:]   # near the end -> slide back to keep the window full
            else:
                page = [a for a in members if a <= anchor][-want:]
                if len(page) < want:
                    page = members[:want]    # near the start -> slide forward
            spans: set[Span] = set()
            for a in page:
                spans |= {Span(self.table, x, 1) for x in self._row_read_addrs(a)}
            if spans:
                self._read_spans(spans)      # read whole entity spans so split entities still decode
            nxt = min((a for a in members if a > page[-1]), default=None)
            prv = max((a for a in members if a < page[0]), default=None)
            return page, nxt, prv

        # scan the paging direction; if short at an edge, slide the window the other way to fill it
        if forward:
            page = self._scan_run(True, anchor, want)
            if 0 < len(page) < want:
                page = sorted(self._scan_run(False, page[0] - 1, want - len(page)) + page)
        else:
            page = self._scan_run(False, anchor, want)
            if 0 < len(page) < want:
                page = sorted(page + self._scan_run(True, page[-1] + 1, want - len(page)))
        if not page:
            return [], None, None
        after = self._scan_run(True, page[-1] + 1, 1)   # a one-register look-ahead each way sets the anchors
        before = self._scan_run(False, page[0] - 1, 1)
        return page, (after[0] if after else None), (before[0] if before else None)

    # --- serialisation -------------------------------------------------------
    def config(self) -> dict[str, Any]:
        return {"table": self.table, "start": self.start, "count": self.count,
                "max_read": self.max_read, "filter": self.filter, "search": self.search}

    def _row(self, addr: int) -> dict[str, Any]:
        cell = self.cells.get((self.table, addr))
        row: dict[str, Any] = {"address": addr, "value": None, "changes": 0, "reads": 0,
                               "last_changed": -1, "error": None}
        if cell is not None:
            row.update(value=cell.value, changes=cell.changes, reads=cell.reads,
                       last_changed=cell.last_changed, error=cell.error,
                       hist=[h["value"] for h in cell.history[-HISTORY_SPARK:]],
                       hist_len=len(cell.history))
        if (self.table, addr) in self._bad:
            row["dead"] = True  # given up on (skipped from reads) — the UI offers a ↻ retry
            if row["error"] is None:
                row["error"] = "not served"  # known dead (a device file's hint), never probed
        if self.device is not None or self.additional:
            row["entity"] = self._entity_overlay(addr)
            if self.filter in _XRAY_FILTERS:
                self._xray_overlay(row, addr)
        if self.additional:
            self._additional_overlay(row, addr)
        return row

    def history(self, table: str, address: int) -> dict[str, Any]:
        """The full recorded history for one register — its distinct-from-previous values with
        the scan index and timestamp each was first seen — for the side panel. The value only
        grows history when the register is actually read (i.e. its page is scanned)."""
        cell = self.cells.get((table, address))
        entity: dict[str, Any] | None = None
        if self.device is not None:
            defn = self._starts.get((table, address)) or self._covered.get((table, address))
            if defn is not None:
                entity = {"name": defn.ha.get("name") or defn.key, "address": defn.address}
        return {"table": table, "address": address,
                "history": list(cell.history) if cell is not None else [],
                "value": cell.value if cell is not None else None,
                "changes": cell.changes if cell is not None else 0, "entity": entity}

    def snapshot(self) -> dict[str, Any]:
        """The current view as rows, for rendering (see full_state for export). Every view is a
        packed page that page() fills and ◀ / ▶ walk: every known register for the plain view —
        refused/dead ones included (write-only registers refuse reads but exist) — or a filtered
        subset (served / mapped / non-zero / changed / their unions / the x-ray projection of every
        table's mappings). The filtered views read past dead registers so the page always fills."""
        base = {"config": self.config(), "scan_index": self.scan_index,
                "last_error": self.last_error, "device": self.device_summary(),
                "meta": dict(self.meta),
                "imported": dict(self.imported["meta"]) if self.imported else None,
                "additional": [{"name": ov.name, "manufacturer": ov.device.manufacturer,
                                "model": ov.device.model} for ov in self.additional],
                "connection": {**self.connection, "connected": self.connected,
                               "error": self.conn_error}}
        return {**base, "rows": [self._row(a) for a in self._page_addrs],
                "at_start": self._page_prev_anchor is None,
                "at_end": self._page_next_anchor is None,
                "next_anchor": self._page_next_anchor, "prev_anchor": self._page_prev_anchor}

    def full_state(self) -> dict[str, Any]:
        """Everything worth saving as a *project*: every remembered cell (all tables), the mapping,
        any additive overlays, the connection, and just the Count / Per-read tuning — NOT the
        table, view position, or filter (those are per-session, so an import doesn't yank you off
        what you're looking at). Round-trips through load_state."""
        cells = [
            {"table": table, "address": cell.address, "value": cell.value,
             "changes": cell.changes, "reads": cell.reads, "last_changed": cell.last_changed,
             "error": cell.error, "illegal": cell.illegal, "history": cell.history}
            for (table, _addr), cell in sorted(self.cells.items())
        ]
        return {"config": {"count": self.count, "max_read": self.max_read},
                "connection": dict(self.connection), "scan_index": self.scan_index,
                "meta": dict(self.meta), "mapping": self.map_doc,
                "additional": [{"name": ov.name, "mapping": ov.doc} for ov in self.additional],
                "cells": cells}

    def load_state(self, data: dict[str, Any]) -> None:
        cfg = data.get("config", {})
        # restore only Count / Per-read (keep the current table, position, and filter); the table
        # was historically in the export too, so still fall back to it for the old single-table 'rows'.
        self.reconfigure(table=self.table, start=self.start, filter_mode=self.filter,
                         count=int(cfg.get("count", self.count)),
                         max_read=int(cfg.get("max_read", self.max_read)))
        self.page_size = self.count   # Count is the rows-per-page in every view -> apply the import
        conn = data.get("connection")
        if isinstance(conn, dict):   # bring the connection settings back (but stay disconnected)
            self.connection = {"mode": str(conn.get("mode", "")), "host": str(conn.get("host", "")),
                               "port": int(conn.get("port") or 502), "device_id": int(conn.get("device_id") or 1),
                               "timeout": float(conn.get("timeout") or 2.0), "retries": int(conn.get("retries") or 0)}
        self.scan_index = int(data.get("scan_index", 0))
        # accept the cross-table 'cells' list, or an older single-table 'rows' export —
        # parsed fully BEFORE anything is replaced, so a malformed file (the caller turns
        # the raised error into a 400) can't leave the session half-wiped
        entries = data.get("cells")
        if entries is None:
            entries = [{**r, "table": cfg.get("table", self.table)} for r in data.get("rows", [])]
        cells: dict[tuple[str, int], Cell] = {}
        bad: set[tuple[str, int]] = set()
        for row in entries:
            table = str(row.get("table", self.table))
            addr = int(row["address"])
            cell = Cell(addr, value=row.get("value"), changes=int(row.get("changes", 0)),
                        reads=int(row.get("reads", 0)), last_changed=int(row.get("last_changed", -1)),
                        error=row.get("error"),
                        illegal=bool(row.get("illegal", row.get("error") == "not served")),
                        history=list(row.get("history") or []))
            cells[(table, addr)] = cell
            if cell.error == "not served":
                bad.add((table, addr))
        self.cells, self._bad, self._misses = cells, bad, {}
        mapping = data.get("mapping")
        if mapping:
            # JSON stringified the mapping's integer 'map'/'flags' keys — restore them, or the
            # schema rejects the whole mapping (which used to be swallowed, losing the mapping).
            self.map_doc, self.device_name = _restore_int_keys(mapping), "imported.yaml"
            try:
                self._reindex()
            except (DeviceSchemaError, yaml.YAMLError, ValueError) as exc:
                self.clear_device()  # a genuinely unparseable mapping — drop it, but say so
                self.last_error = f"imported mapping could not be parsed: {' '.join(str(exc).split())}"
        else:
            self.clear_device()
        # additive overlays ride in exports too; one that no longer parses is dropped, but said so
        self.additional = []
        for item in data.get("additional") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "overlay.yaml")
            try:
                self._add_overlay(name, _restore_int_keys(item["mapping"]))
            except (DeviceSchemaError, yaml.YAMLError, ValueError, KeyError, TypeError) as exc:
                self.last_error = (f"additional mapping {name} could not be parsed: "
                                   f"{' '.join(str(exc).split())}")
        meta = data.get("meta")
        if isinstance(meta, dict):
            self.set_meta(meta.get("manufacturer"), meta.get("model"))
        elif self.device is not None:  # an older export without meta: seed from its mapping
            self.set_meta(self.device.manufacturer, self.device.model)
        else:
            self.set_meta("", "")
        # remember the imported mapping for the session, so the dropdown can switch away
        # from it (a bundled file, or none) and back without losing it
        self.imported = ({"mapping": copy.deepcopy(self.map_doc), "meta": dict(self.meta)}
                         if self.device is not None else None)

    def generate_yaml(self, manufacturer: str, model: str, addresses: list[int]) -> str:
        """A device file from the mapping plus any bare selected registers (see
        generate_device_yaml)."""
        return generate_device_yaml(self, manufacturer, model, addresses)

    # --- editable mapping (a device-file document) ---------------------------
    def load_device(self, yaml_text: str, name: str, *, additive: bool = False) -> dict[str, Any] | None:
        """Load a device file as the editable mapping, replacing any current one — or, with
        ``additive`` while anything is loaded, keep everything and stack the file underneath
        as a read-only comparison overlay (with nothing loaded yet, additive is a plain load).
        Raises DeviceSchemaError / yaml.YAMLError on a bad file (the current state is kept)."""
        doc = yaml.safe_load(yaml_text)
        if not isinstance(doc, dict):
            raise DeviceSchemaError("device file must be a YAML mapping")
        if additive and (self.device is not None or self.additional):
            self._add_overlay(name, doc)
            return self.device_summary()
        prev, prev_name = self.map_doc, self.device_name
        self.map_doc, self.device_name = doc, name
        try:
            self._reindex()
        except (DeviceSchemaError, yaml.YAMLError, ValueError):
            self.map_doc, self.device_name = prev, prev_name
            self._reindex()
            raise
        self.additional = []  # a plain load replaces the comparison overlays too
        if self.device is not None:  # seed the generate stamp from the file (editable after)
            self.set_meta(self.device.manufacturer, self.device.model)
        return self.device_summary()

    def _add_overlay(self, name: str, doc: dict[str, Any]) -> None:
        """Parse and slot in an additive overlay: re-loading a name refreshes it in place
        (same priority), a new name joins at the end (lowest priority). Deliberately NOT
        applied from an overlay: the generate stamp (it stays the editable mapping's) and
        the file's bad_addresses — another model's dead registers may be alive here."""
        device = parse_device(doc, name)  # raises on a bad file; nothing touched yet
        overlay = Overlay(name, doc, device, *_index_entities(device))
        for i, present in enumerate(self.additional):
            if present.name == name:
                self.additional[i] = overlay
                return
        self.additional.append(overlay)

    def set_meta(self, manufacturer: Any, model: Any) -> None:
        """The manufacturer/model the UI shows and a generated file gets stamped with."""
        self.meta = {"manufacturer": str(manufacturer or "").strip(),
                     "model": str(model or "").strip()}
        self._sync_imported()

    def _sync_imported(self) -> None:
        """While the imported mapping is the active one, mirror every edit into the
        remembered slot — switching away and back must never lose work."""
        if self.device_name == "imported.yaml" and self.imported is not None:
            self.imported = {"mapping": copy.deepcopy(self.map_doc), "meta": dict(self.meta)}

    def load_imported(self, *, additive: bool = False) -> dict[str, Any] | None:
        """Re-activate the remembered imported mapping (the dropdown's 'imported' entry),
        with the stamp it carried — or, with ``additive`` while anything is loaded, stack
        it underneath as an overlay; raises when nothing was imported this session."""
        if not self.imported:
            raise DeviceSchemaError("no imported mapping to switch back to")
        if additive and (self.device is not None or self.additional):
            self._add_overlay("imported.yaml", copy.deepcopy(self.imported["mapping"]))
            return self.device_summary()
        prev, prev_name = self.map_doc, self.device_name
        self.map_doc, self.device_name = copy.deepcopy(self.imported["mapping"]), "imported.yaml"
        try:
            self._reindex()
        except (DeviceSchemaError, yaml.YAMLError, ValueError):
            self.map_doc, self.device_name = prev, prev_name
            self._reindex()
            raise
        self.additional = []  # a plain load replaces the comparison overlays too
        self.set_meta(self.imported["meta"].get("manufacturer"), self.imported["meta"].get("model"))
        return self.device_summary()

    def set_mapping(self, table: str, address: int, fields: dict[str, Any]) -> dict[str, Any] | None:
        """Map (or remap) the entity that starts at ``address`` on ``table`` from the
        UI editor fields. The result is validated by the real schema; on failure the
        previous mapping is restored and a DeviceSchemaError is raised."""
        if table not in TABLES:
            raise DeviceSchemaError(f"unknown table {table!r}")
        entity = _entity_from_fields(table, {**fields, "address": int(address)})
        prev = copy.deepcopy(self.map_doc)
        doc: dict[str, Any] = copy.deepcopy(self.map_doc) if self.map_doc else {
            "device": {"manufacturer": self.meta["manufacturer"] or "TODO",
                       "model": self.meta["model"] or "TODO"}}
        section = doc.setdefault(table, {})
        # drop any existing entity starting here (a remap), then add under a fresh key
        for key in [k for k, e in section.items() if isinstance(e, dict) and e.get("address") == address]:
            del section[key]
        section[_unique_key(doc, table, address)] = entity
        self.map_doc = doc
        try:
            self._reindex()
        except (DeviceSchemaError, yaml.YAMLError, ValueError) as exc:
            self.map_doc = prev
            self._reindex()
            raise DeviceSchemaError(" ".join(str(exc).split())) from exc
        self._sync_imported()
        return self.device_summary()

    def copy_mapping(self, table: str, address: int) -> dict[str, Any] | None:
        """Copy the sibling table's entity that starts at ``address`` onto ``table`` at the
        same address — the x-ray views' one-click way to adopt a compatible foreign mapping.
        The copy keeps the raw spec but gets its own key and a unique display name (the
        original stays mapped on the sibling, and the schema refuses duplicate names);
        the result is validated like any edit, restoring the previous mapping on failure."""
        if table not in TABLES:
            raise DeviceSchemaError(f"unknown table {table!r}")
        sib = _SIBLING[table]
        src = self._starts.get((sib, address))
        if src is None:
            raise DeviceSchemaError(f"no {sib} mapping starts at address {address}")
        if any((table, a) in self._covered for a in range(src.span.start, src.span.end)):
            raise DeviceSchemaError(
                f"{table} already maps a register in {src.span.start}..{src.span.end - 1}")
        spec = copy.deepcopy((self.map_doc or {}).get(sib, {}).get(src.key))
        if not isinstance(spec, dict):  # defensive: the indexes always mirror the doc
            raise DeviceSchemaError(f"no raw mapping for {sib}.{src.key}")
        prev = copy.deepcopy(self.map_doc)
        doc: dict[str, Any] = copy.deepcopy(self.map_doc) or {}
        # taken display names, exactly as the schema's uniqueness rule computes them
        used = list(self.device.entities) + list(getattr(self.device, "templates", ()) or ())
        names = {i.ha.get("name") or derive_name(i.key) for i in used}
        base = (spec.get("ha") or {}).get("name") or derive_name(src.key)
        name, n = f"{base} ({table})", 2
        while name in names:
            name, n = f"{base} ({table} {n})", n + 1
        spec.setdefault("ha", {})["name"] = name
        spec["address"] = address
        doc.setdefault(table, {})[_unique_key(doc, table, address)] = spec
        self.map_doc = doc
        try:
            self._reindex()
        except (DeviceSchemaError, yaml.YAMLError, ValueError) as exc:
            self.map_doc = prev
            self._reindex()
            raise DeviceSchemaError(" ".join(str(exc).split())) from exc
        self._sync_imported()
        return self.device_summary()

    def adopt_mapping(self, table: str, address: int) -> dict[str, Any] | None:
        """Copy an additive overlay's entity that starts at ``address`` on ``table`` into
        the editable mapping — the overlays' twin of copy_mapping (the grey cells' ⧉).
        The first overlay (in priority order) with an entity starting there provides the
        raw spec; the copy keeps its display name unless that name is taken (then it gets
        a numbered suffix, since the schema refuses duplicates), and is validated like any
        edit, restoring the previous mapping on failure."""
        if table not in TABLES:
            raise DeviceSchemaError(f"unknown table {table!r}")
        src = spec = None
        for overlay in self.additional:
            src = overlay.starts.get((table, address))
            if src is not None:
                spec = copy.deepcopy(overlay.doc.get(table, {}).get(src.key))
                break
        if src is None:
            raise DeviceSchemaError(f"no additional mapping starts at {table} address {address}")
        if not isinstance(spec, dict):  # defensive: the indexes always mirror the doc
            raise DeviceSchemaError(f"no raw mapping for {table} address {address}")
        if any((table, a) in self._covered for a in range(src.span.start, src.span.end)):
            raise DeviceSchemaError(
                f"{table} already maps a register in {src.span.start}..{src.span.end - 1}")
        prev = copy.deepcopy(self.map_doc)
        doc: dict[str, Any] = copy.deepcopy(self.map_doc) if self.map_doc else {
            "device": {"manufacturer": self.meta["manufacturer"] or "TODO",
                       "model": self.meta["model"] or "TODO"}}
        # taken display names, exactly as the schema's uniqueness rule computes them
        used = (list(self.device.entities) + list(getattr(self.device, "templates", ()) or ())
                if self.device is not None else [])
        names = {i.ha.get("name") or derive_name(i.key) for i in used}
        base = (spec.get("ha") or {}).get("name") or derive_name(src.key)
        if base in names:
            name, n = f"{base} (2)", 3
            while name in names:
                name, n = f"{base} ({n})", n + 1
            spec.setdefault("ha", {})["name"] = name
        spec["address"] = address
        doc.setdefault(table, {})[_unique_key(doc, table, address)] = spec
        self.map_doc = doc
        try:
            self._reindex()
        except (DeviceSchemaError, yaml.YAMLError, ValueError) as exc:
            self.map_doc = prev
            self._reindex()
            raise DeviceSchemaError(" ".join(str(exc).split())) from exc
        self._sync_imported()
        return self.device_summary()

    def remove_mapping(self, table: str, address: int) -> dict[str, Any] | None:
        """Unmap the entity that starts at ``address`` on ``table``."""
        if not self.map_doc:
            return None
        doc = copy.deepcopy(self.map_doc)
        section = doc.get(table, {})
        for key in [k for k, e in section.items() if isinstance(e, dict) and e.get("address") == address]:
            del section[key]
        if not section:
            doc.pop(table, None)
        if any(isinstance(doc.get(t), dict) and doc[t] for t in TABLES):
            self.map_doc = doc
            self._reindex()
            self._sync_imported()
        else:
            self.clear_device()  # nothing mapped anymore -> drop the overlay entirely
        return self.device_summary()

    def clear_device(self) -> None:
        self.map_doc, self.device, self.device_name = None, None, ""
        self._starts, self._covered = {}, {}

    def clear_devices(self) -> None:
        """The dropdown's — none —: drop the editable mapping AND every additive overlay
        (everything mapping-shaped), keeping the stats, history and the dead list."""
        self.clear_device()
        self.additional = []

    def clear_all(self) -> None:
        """Start over: drop the mapping, every table's per-register stats and value history,
        and the given-up-on (dead) register list. This is the *only* thing that wipes the stats
        and the dead list — a reconnect keeps them — so it's also how you re-probe registers you
        earlier marked dead (they stay skipped for good until cleared here)."""
        self.clear_devices()
        self.cells.clear()
        self._bad.clear()
        self._misses.clear()
        self.imported = None
        self.set_meta("", "")
        self.scan_index = 0
        self.last_error = None
        self._clear_page()

    def _reindex(self) -> None:
        """Reparse the mapping document into the entity indexes (or clear when empty)."""
        self._starts, self._covered = {}, {}
        if not self.map_doc:
            self.device = None
            return
        device = parse_device(self.map_doc, self.device_name or "mapping.yaml")
        self.device = device
        # apply the device file's known-dead list: those registers start out given up on (skipped
        # + hidden), so loading a project you were working on doesn't re-probe what you already know
        # the device refuses. Newly-found dead ones join _bad and are written back on generate.
        self._bad |= device.bad_addresses
        self._starts, self._covered = _index_entities(device)

    def device_summary(self) -> dict[str, Any] | None:
        if self.device is None:
            return None
        tables: dict[str, dict[str, int]] = {}
        for e in self.device.entities:
            t = tables.setdefault(e.table, {"min": e.address, "max": e.span.end - 1, "entities": 0})
            t["min"], t["max"] = min(t["min"], e.address), max(t["max"], e.span.end - 1)
            t["entities"] += 1
        return {"name": self.device_name, "manufacturer": self.device.manufacturer,
                "model": self.device.model, "tables": tables}

    def _entity_overlay(self, addr: int) -> dict[str, Any] | None:
        """The mapping's info for one address on the current table (for the overlay
        columns and the editor). ``address`` is the entity's start, so a click on any
        of its registers edits the same entity; ``spec`` is the raw mapping for prefill."""
        start = self._starts.get((self.table, addr))
        if start is not None:
            decoded, err = self._decode_entity(start)
            spec = (self.map_doc or {}).get(start.table, {}).get(start.key)
            return {"key": start.key, "name": start.ha.get("name") or start.key,
                    "type": start.type, "count": start.count, "platform": start.platform,
                    "address": start.address, "spec": spec,
                    "decoded": _jsonable(decoded), "decode_error": err}
        cover = self._covered.get((self.table, addr))
        if cover is not None:
            return {"continuation": True, "name": cover.ha.get("name") or cover.key,
                    "address": cover.address}
        return None

    def _xray_overlay(self, row: dict[str, Any], addr: int) -> None:
        """The x-ray extras for one row: ``xmap`` is the sibling (same-width) table's mapping
        at this address, decoded against the *current* table's registers — the UI shows it
        muted, as if it were mapped here; ``xother`` names the non-compatible tables'
        mappings, which the UI only reveals on hover."""
        sib = _SIBLING[self.table]
        start = self._starts.get((sib, addr))
        if start is not None:
            decoded, err = self._decode_entity(start, value_table=self.table)
            row["xmap"] = {"table": sib, "name": start.ha.get("name") or start.key,
                           "type": start.type, "count": start.count,
                           "decoded": _jsonable(decoded), "decode_error": err}
        else:
            cover = self._covered.get((sib, addr))
            if cover is not None:
                row["xmap"] = {"table": sib, "name": cover.ha.get("name") or cover.key,
                               "continuation": True}
        others = [{"table": t, "name": d.ha.get("name") or d.key}
                  for t in TABLES
                  if t not in (self.table, sib)
                  and (d := self._covered.get((t, addr))) is not None]
        if others:
            row["xother"] = others

    def _additional_overlay(self, row: dict[str, Any], addr: int) -> None:
        """The additive overlays' hits at this address, in priority (load) order, as
        ``amaps``. Outside the x-ray views only the current table's entities appear; the
        x-ray views treat each overlay exactly like the mapping's own x-ray — its
        same-width sibling entities decoded against the *current* table's registers, its
        non-compatible tables' entities named for the hover title (``other``). The UI
        fills a still-empty cell with the first hit — grey, tagged with this register's
        own address (it maps HERE, unlike a sibling projection) — and corners the rest
        after any x-ray entries."""
        sib = _SIBLING[self.table]
        xray = self.filter in _XRAY_FILTERS
        hits: list[dict[str, Any]] = []
        for overlay in self.additional:
            for t in (self.table, sib) if xray else (self.table,):
                start = overlay.starts.get((t, addr))
                if start is not None:
                    decoded, err = self._decode_entity(start, value_table=self.table)
                    hits.append({"src": overlay.name, "table": t,
                                 "name": start.ha.get("name") or start.key,
                                 "type": start.type, "count": start.count,
                                 "decoded": _jsonable(decoded), "decode_error": err})
                    continue
                cover = overlay.covered.get((t, addr))
                if cover is not None:
                    hits.append({"src": overlay.name, "table": t, "continuation": True,
                                 "name": cover.ha.get("name") or cover.key})
            if xray:
                hits.extend({"src": overlay.name, "table": t, "other": True,
                             "name": d.ha.get("name") or d.key}
                            for t in TABLES
                            if t not in (self.table, sib)
                            and (d := overlay.covered.get((t, addr))) is not None)
        if hits:
            row["amaps"] = hits

    def _decode_entity(self, defn: EntityDef, value_table: str | None = None) -> tuple[Any, str | None]:
        """Decode an entity through the integration's codec from the scanned raw words
        of its span; (None, reason) when its registers aren't all scanned/served. The
        x-ray views pass ``value_table`` to decode a sibling table's entity against the
        *current* table's registers instead of its own."""
        table = value_table or defn.table
        words: list[int] = []
        for a in range(defn.span.start, defn.span.end):
            cell = self.cells.get((table, a))
            if cell is None or cell.value is None:
                return None, "unread"
            words.append(cell.value)
        raw = [bool(w) for w in words] if defn.table in BIT_TABLES else words
        try:
            return codec.decode(defn, raw), None
        except Exception as exc:
            return None, f"decode error: {exc}"


def _jsonable(value: Any) -> Any:
    """codec.decode may return a datetime.time etc.; keep JSON to primitives."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _restore_int_keys(node: Any) -> Any:
    """JSON turns a mapping's integer dict keys into strings; a device file's ``map`` / ``flags``
    need real int keys back, or the schema rejects them. Recursively coerce the (all-digit) keys
    under any ``map`` / ``flags`` back to int (idempotent — real int keys are left alone)."""
    if isinstance(node, dict):
        out: dict[Any, Any] = {}
        for k, v in node.items():
            if k in ("map", "flags") and isinstance(v, dict):
                out[k] = {(int(mk) if isinstance(mk, str) and mk.isdigit() else mk): mv
                          for mk, mv in v.items()}
            else:
                out[k] = _restore_int_keys(v)
        return out
    if isinstance(node, list):
        return [_restore_int_keys(x) for x in node]
    return node


# --- building a device-file entity from the UI editor -------------------------
def _num(value: Any) -> int | float:
    """A YAML number from an editor string: int when it has no fractional part."""
    f = float(value)
    return int(f) if f.is_integer() else f


def _parse_map_text(text: str) -> dict[int, str]:
    """Parse the editor's ``map`` field — ``0: Off, 1: On`` or one ``value: label``
    per line (values may be hex like ``0x10``) — into a device-file map."""
    out: dict[int, str] = {}
    for part in re.split(r"[\n,]", text):
        part = part.strip()
        if not part:
            continue
        raw_key, sep, label = part.partition(":")
        if not sep or not label.strip():
            raise DeviceSchemaError(f"map entry {part!r} must be 'value: label'")
        try:
            key = int(raw_key.strip(), 0)
        except ValueError:
            raise DeviceSchemaError(f"map key {raw_key.strip()!r} is not an integer") from None
        out[key] = label.strip()
    if not out:
        raise DeviceSchemaError("map is empty")
    return out


def _parse_num_list(text: str) -> list[int | float]:
    """Parse the editor's ``sum_scale`` field — comma/space-separated numbers — into a
    device-file weight list (ints stay ints, for the writable positive-integer form)."""
    nums = [_num(p) for p in re.split(r"[,\s]+", text.strip()) if p]
    if not nums:
        raise DeviceSchemaError("sum_scale must be a list of numbers, e.g. 1, 0.1")
    return nums


def _num_or_str(value: str) -> int | float | str:
    """A write_value payload: a number, or (e.g. a Jinja template) a string."""
    try:
        return _num(value)
    except ValueError:
        return value


def _merge_advanced(entity: dict[str, Any], text: str) -> dict[str, Any]:
    """Merge the editor's free-form *advanced* YAML/JSON block (any device-file key the
    dedicated fields don't cover: swap, groups, scan_interval, write tuning, extra ha
    fields, …) into the entity. Dedicated fields win on a clash; the whole result is still
    validated by the real schema when the document is reparsed."""
    if not text.strip():
        return entity
    try:
        extra = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise DeviceSchemaError(f"advanced block is not valid YAML/JSON: {exc}") from None
    if extra is None:
        return entity
    if not isinstance(extra, dict):
        raise DeviceSchemaError("advanced block must be a mapping of extra keys")
    ha_extra = extra.pop("ha", None)
    merged = {**extra, **entity}  # a dedicated field wins over the same key in advanced
    if isinstance(ha_extra, dict):
        merged["ha"] = {**ha_extra, **entity["ha"]}
    return merged


def _entity_from_fields(table: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Turn the editor's fields into a device-file entity mapping (validated later by
    the schema when the whole document is reparsed)."""
    address = int(fields["address"])
    platform = str(fields.get("platform") or "sensor").strip()
    entity: dict[str, Any] = {"address": address}

    if table not in BIT_TABLES:  # bit tables are always bool; word tables carry a type
        typ = str(fields.get("type") or "").strip()
        if platform == "text":
            typ = "string"
        elif platform == "time":
            typ = "time"
        if typ and typ != "uint16":
            entity["type"] = typ
        if typ == "string":
            entity["count"] = int(fields.get("count") or 1)
        if str(fields.get("swap") or "").strip():
            entity["swap"] = str(fields["swap"]).strip()
        if str(fields.get("scale") or "").strip():
            entity["multiplier"] = _num(fields["scale"])
        if str(fields.get("offset") or "").strip():
            entity["offset"] = _num(fields["offset"])
        if str(fields.get("sum_scale") or "").strip():
            entity["sum_scale"] = _parse_num_list(str(fields["sum_scale"]))
        if str(fields.get("mask") or "").strip():
            entity["mask"] = int(str(fields["mask"]).strip(), 0)
        if str(fields.get("map") or "").strip():
            entity["map"] = _parse_map_text(str(fields["map"]))
        if str(fields.get("flags") or "").strip():
            entity["flags"] = _parse_map_text(str(fields["flags"]))
        for key in ("on_value", "off_value"):
            if str(fields.get(key) or "").strip():
                entity[key] = int(str(fields[key]).strip(), 0)  # register values: hex welcome, like mask
    if str(fields.get("write_value") or "").strip():  # a button's payload (valid on any table)
        entity["write_value"] = _num_or_str(str(fields["write_value"]).strip())

    ha: dict[str, Any] = {"platform": platform}
    if str(fields.get("name") or "").strip():
        ha["name"] = str(fields["name"]).strip()
    if str(fields.get("unit") or "").strip():
        ha["unit"] = str(fields["unit"]).strip()
    for key in ("min", "max", "step"):
        if str(fields.get(key) or "").strip():
            ha[key] = _num(fields[key])
    if str(fields.get("precision") or "").strip():
        ha["precision"] = int(fields["precision"])
    if str(fields.get("device_class") or "").strip():
        ha["device_class"] = str(fields["device_class"]).strip()
    if str(fields.get("state_class") or "").strip():
        ha["state_class"] = str(fields["state_class"]).strip()
    if str(fields.get("entity_category") or "").strip():
        ha["entity_category"] = str(fields["entity_category"]).strip()
    if str(fields.get("icon") or "").strip():
        ha["icon"] = str(fields["icon"]).strip()
    entity["ha"] = ha
    return _merge_advanced(entity, str(fields.get("advanced") or ""))


def _unique_key(doc: dict[str, Any], table: str, address: int) -> str:
    """A stable, unique entity key for a mapped register: ``<table>_<hex addr>``."""
    existing = {k for t in TABLES if isinstance(doc.get(t), dict) for k in doc[t]}
    base = f"{table}_{address:04x}"
    key, n = base, 2
    while key in existing:
        key, n = f"{base}_{n}", n + 1
    return key


def list_device_files() -> list[dict[str, str]]:
    """Bundled device_configs, for the UI dropdown: filename + 'manufacturer model'."""
    out: list[dict[str, str]] = []
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        if path.stem == "test":
            continue
        try:
            manufacturer, model = _device_label(path, path.name)
        except DeviceSchemaError:
            continue
        out.append({"file": path.name, "label": f"{manufacturer} {model}"})
    return out


def decoded_views(regs: list[int]) -> list[dict[str, str]]:
    """Common multi-register interpretations, labelled like device-file types — the
    'what could this be?' helper (ported from modbus_cli). Big-endian words; the
    ``swap: word`` rows show a word-swapped device."""
    views: list[dict[str, str]] = []
    if len(regs) in (2, 4):
        bits = 16 * len(regs)
        float_fmt = ">f" if len(regs) == 2 else ">d"
        for suffix, words in (("", regs), (" (swap: word)", list(reversed(regs)))):
            raw = struct.pack(f">{len(words)}H", *words)
            views.append({"type": f"uint{bits}{suffix}", "value": str(int.from_bytes(raw, "big"))})
            views.append({"type": f"int{bits}{suffix}", "value": str(int.from_bytes(raw, "big", signed=True))})
            views.append({"type": f"float{bits}{suffix}", "value": repr(struct.unpack(float_fmt, raw)[0])})
    if len(regs) >= 2:
        raw = struct.pack(f">{len(regs)}H", *regs)
        views.append({"type": "string", "value": "".join(chr(b) if 32 <= b < 127 else "·" for b in raw)})
    return views


def _reduce_bad_addresses(
    reads_by_table: dict[str, set[int]], bad_by_table: dict[str, set[int]]
) -> dict[str, list[int]]:
    """Cut each table's dead-register list down to the few the integration actually needs
    to partition its reads: one per gap between consecutive read addresses, and none
    outside the read range.

    The planner consults a hole only when deciding whether to bridge the gap between two
    needed registers, and only asks whether that gap holds *any* hole (planner._can_merge:
    ``not any((table, a) in holes ...)``) — so the first dead address in a gap is enough to
    break the bridge and the rest are redundant. A dead address before the first / after
    the last read register never sits inside a bridged gap, so it is dropped entirely.

    Keeping every dead register (there can be tens of thousands from a full scan) would
    bloat the device file without changing a single read; this leaves at most one entry
    per gap between the ~hundreds of registers a device actually maps."""
    out: dict[str, list[int]] = {}
    for table, reads in reads_by_table.items():
        bad = bad_by_table.get(table)
        if not reads or not bad:
            continue
        reads_sorted = sorted(reads)
        kept: list[int] = []
        last_gap = -1
        for a in sorted(bad):
            if not reads_sorted[0] < a < reads_sorted[-1] or a in reads:
                continue  # outside the read range (never read), or itself a read register
            gap = bisect.bisect_left(reads_sorted, a)  # a lies in gap (reads[gap-1], reads[gap])
            if gap != last_gap:  # first dead address in this gap is enough; skip the rest
                kept.append(a)
                last_gap = gap
        if kept:
            out[table] = kept
    return out


def generate_device_yaml(scanner: Scanner, manufacturer: str, model: str,
                         addresses: list[int]) -> str:
    """Emit a valid device file from the editable mapping (every mapped entity, across
    all tables) plus a bare sensor for each *selected* served register that isn't mapped
    yet, with a pruned ``bad_addresses`` hint (see ``_reduce_bad_addresses``: only the
    dead registers that fall between mapped ones, all the planner needs). A skeleton to
    refine by hand."""
    doc = copy.deepcopy(scanner.map_doc) if scanner.map_doc else {}
    device = dict(doc.get("device") or {})
    device["manufacturer"] = manufacturer or device.get("manufacturer") or "TODO"
    device["model"] = model or device.get("model") or "TODO"

    sections: dict[str, dict[str, Any]] = {t: dict(doc.get(t) or {}) for t in TABLES}
    existing = {k for t in TABLES for k in sections[t]}
    table = scanner.table

    # Every address the generated file will actually read: all mapped entity addresses
    # (across tables), plus the bare sensors added below for selected served registers.
    reads: dict[str, set[int]] = {t: set() for t in TABLES}
    for (t, a) in scanner._covered:
        if t in reads:
            reads[t].add(a)

    for addr in sorted(addresses):
        if (table, addr) in scanner._covered:  # already mapped explicitly
            continue
        cell = scanner.cells.get((table, addr))
        if cell is None or cell.error is not None or cell.value is None:
            continue
        key = f"{table}_{addr:04x}"
        if key in existing:
            continue
        entity: dict[str, Any] = {"address": addr,
                                  "ha": {"platform": "sensor", "name": f"{table.capitalize()} 0x{addr:04X}"}}
        if cell.changes:  # something that moves is probably a live measurement
            entity["ha"]["state_class"] = "measurement"
        sections[table][key] = entity
        existing.add(key)
        reads[table].add(addr)

    # bad_addresses only exist to tell the planner where it must not bridge a read, so
    # prune the union of scanned-dead and any already in the file down to the few that
    # matter (one per gap between read registers) — see _reduce_bad_addresses.
    bad: dict[str, set[int]] = {t: set() for t in TABLES}
    for t, addrs in (device.get("bad_addresses") or {}).items():
        if t in bad:
            bad[t] |= {int(a) for a in addrs}
    for (t, a) in scanner._bad:
        if t in bad:
            bad[t].add(a)
    reduced = _reduce_bad_addresses(reads, bad)
    device.pop("bad_addresses", None)  # drop any stale (full) list from a loaded file
    if reduced:
        device["bad_addresses"] = {t: reduced[t] for t in TABLES if t in reduced}

    # Canonical section order, matching the bundled configs (augment.emit): device, then the
    # register tables, then template, and the (often long) translations catalog last.
    out: dict[str, Any] = {"device": device}
    for t in TABLES:
        if sections[t]:
            out[t] = sections[t]
    if "template" in doc:
        out["template"] = doc["template"]
    if "translations" in doc:
        out["translations"] = doc["translations"]

    header = (
        "# Generated by support/modbus_scanner — a skeleton to refine by hand.\n"
        "# Mapped entities are yours; any bare sensors are served registers you selected\n"
        "# (set real names/types/scale, promote pairs to float32/int32). See docs/device_files.md.\n"
    )
    return header + yaml.safe_dump(out, sort_keys=False, allow_unicode=True, default_flow_style=False)


# --- web server ---------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:  # quiet; this is a local tool
        pass

    @property
    def _scanner(self) -> Scanner:
        return self.server.scanner  # type: ignore[attr-defined]

    @property
    def _lock(self) -> threading.Lock:
        return self.server.lock  # type: ignore[attr-defined]

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")  # always serve a fresh UI / data
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: Any, status: int = 200) -> None:
        self._send(json.dumps(payload).encode(), "application/json", status)

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send((HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            with self._lock:
                self._json(self._scanner.snapshot())
        elif self.path == "/api/export":
            with self._lock:
                self._json(self._scanner.full_state())
        elif self.path == "/api/devices":
            self._json({"devices": list_device_files()})
        else:
            self._send(b"not found", "text/plain", 404)

    def do_POST(self) -> None:
        try:
            body = self._read_body()
        except (ValueError, OSError):
            self._json({"error": "bad request body"}, 400)
            return
        with self._lock:
            if self.path == "/api/scan":
                self._scanner.scan()
                self._json(self._scanner.snapshot())
            elif self.path == "/api/connect":
                self._scanner.connect(
                    mode=str(body.get("mode", "tcp")),
                    host=str(body.get("host", "")).strip(),
                    port=int(body.get("port") or 502),
                    device_id=int(body.get("device_id") or 1),
                    timeout=float(body.get("timeout") or 2.0),
                    retries=int(body.get("retries") or 0),
                )
                self._json(self._scanner.snapshot())
            elif self.path == "/api/disconnect":
                self._scanner.disconnect()
                self._json(self._scanner.snapshot())
            elif self.path == "/api/config":
                self._scanner.reconfigure(
                    table=body.get("table", self._scanner.table),
                    start=int(body.get("start", self._scanner.start)),
                    count=int(body.get("count", self._scanner.count)),
                    max_read=int(body.get("max_read", self._scanner.max_read)),
                    filter_mode=str(body.get("filter", self._scanner.filter)),
                    page_size=int(body.get("page_size") or self._scanner.page_size),
                    search=str(body.get("search", self._scanner.search)),
                )
                # fill from the requested start; if nothing is shown there (say, a switch to a
                # table that serves nothing at this position), fall back to the first page
                self._scanner.open_page()
                self._json(self._scanner.snapshot())
            elif self.path == "/api/page":
                self._scanner.page(forward=bool(body.get("forward", True)),
                                   anchor=int(body.get("anchor", 0)))
                self._json(self._scanner.snapshot())
            elif self.path == "/api/decode":
                regs = [int(v) for v in body.get("registers", [])]
                self._json({"views": decoded_views(regs)})
            elif self.path == "/api/history":
                self._json(self._scanner.history(
                    str(body.get("table", self._scanner.table)), int(body.get("address") or 0)))
            elif self.path == "/api/retry":
                self._scanner.retry_address(
                    str(body.get("table", self._scanner.table)), int(body.get("address") or 0))
                self._json(self._scanner.snapshot())
            elif self.path == "/api/meta":
                self._scanner.set_meta(body.get("manufacturer"), body.get("model"))
                self._json(self._scanner.snapshot())
            elif self.path == "/api/generate":
                yaml_text = self._scanner.generate_yaml(
                    body.get("manufacturer", ""), body.get("model", ""),
                    [int(a) for a in body.get("addresses", [])],
                )
                self._json({"yaml": yaml_text})
            elif self.path == "/api/import":
                try:
                    self._scanner.load_state(body)
                except (DeviceSchemaError, yaml.YAMLError, ValueError,
                        KeyError, TypeError, AttributeError) as exc:
                    self._json({"error": f"not a scanner project export: {exc}"}, 400)
                    return
                self._scanner.open_page()  # fill the page (offline too), recovering if the saved start is too high
                self._json(self._scanner.snapshot())
            elif self.path in ("/api/map", "/api/unmap", "/api/copymap", "/api/adopt"):
                try:
                    table = str(body.get("table", self._scanner.table))
                    address = int(body["address"])
                    if self.path == "/api/map":
                        self._scanner.set_mapping(table, address, body)
                    elif self.path == "/api/copymap":
                        self._scanner.copy_mapping(table, address)
                    elif self.path == "/api/adopt":
                        self._scanner.adopt_mapping(table, address)
                    else:
                        self._scanner.remove_mapping(table, address)
                except (DeviceSchemaError, yaml.YAMLError, ValueError, KeyError) as exc:
                    self._json({"error": " ".join(str(exc).split())}, 400)
                    return
                self._json(self._scanner.snapshot())
            elif self.path == "/api/device":
                try:
                    additive = bool(body.get("additive"))
                    if body.get("imported"):
                        self._scanner.load_imported(additive=additive)
                    elif body.get("yaml") is not None:
                        self._scanner.load_device(body["yaml"], body.get("name", "uploaded.yaml"),
                                                  additive=additive)
                    else:
                        file = str(body.get("file", ""))
                        path = CONFIG_DIR / file
                        if Path(file).name != file or not path.is_file():
                            self._json({"error": "no such device file"}, 404)
                            return
                        self._scanner.load_device(path.read_text(encoding="utf-8"), path.name,
                                                  additive=additive)
                except (DeviceSchemaError, yaml.YAMLError, ValueError, KeyError) as exc:
                    self._json({"error": " ".join(str(exc).split())}, 400)
                    return
                self._json(self._scanner.snapshot())
            elif self.path == "/api/device/clear":
                self._scanner.clear_devices()
                self._json(self._scanner.snapshot())
            elif self.path == "/api/clear":
                self._scanner.clear_all()
                self._json(self._scanner.snapshot())
            else:
                self._json({"error": "not found"}, 404)


def serve(scanner: Scanner, host: str, port: int, *, open_browser: bool = True) -> None:
    server = ThreadingHTTPServer((host, port), _Handler)
    server.scanner = scanner  # type: ignore[attr-defined]
    server.lock = threading.Lock()  # type: ignore[attr-defined]
    url = f"http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}"
    print(f"modbus-scanner on {url}  (Ctrl-C to stop)")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        scanner._teardown()
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", help="gateway hostname or IP — optional; the connection "
                        "(host/port/id, or Demo) is also settable live in the UI")
    parser.add_argument("--port", type=int, default=502, help="gateway TCP port (default 502)")
    parser.add_argument("--device-id", "--id", type=lambda s: int(s, 0), default=1,
                        help="Modbus unit id behind the gateway (default 1)")
    parser.add_argument("--timeout", type=float, default=2.0, help="seconds per request")
    parser.add_argument("--retries", type=int, default=0, help="pymodbus retries per request")
    parser.add_argument("--table", choices=TABLES, default="holding", help="start on this table")
    parser.add_argument("--start", type=lambda s: int(s, 0), default=0, help="first address")
    parser.add_argument("--count", type=lambda s: int(s, 0), default=64, help="how many addresses")
    parser.add_argument("--max-read", type=int, default=64, help="addresses per read (max_register_read)")
    parser.add_argument("--device", help="load a device file as the editable mapping (a path, or a "
                        "device_configs basename); also loadable live in the UI")
    parser.add_argument("--demo", action="store_true", help="simulated device — no gateway needed")
    parser.add_argument("--web-host", default="127.0.0.1", help="bind address for the UI")
    parser.add_argument("--web-port", type=int, default=8765, help="UI port (default 8765)")
    parser.add_argument("--no-open", action="store_true", help="do not open a browser")
    args = parser.parse_args(argv)

    scanner = Scanner(table=args.table, start=args.start,
                      count=args.count, max_read=args.max_read)
    if args.demo:
        scanner.connect(mode="demo")
    elif args.host:
        scanner.connect(mode="tcp", host=args.host, port=args.port, device_id=args.device_id,
                        timeout=args.timeout, retries=args.retries)
        if not scanner.connected:
            print(scanner.conn_error, file=sys.stderr)  # not fatal — reconnect in the UI
    # else: start disconnected; set host/port/id in the UI's Connection panel and Connect.
    if args.device:
        path = Path(args.device)
        if not path.is_file():
            for cand in (CONFIG_DIR / args.device, CONFIG_DIR / f"{args.device}.yaml"):
                if cand.is_file():
                    path = cand
                    break
        summary = scanner.load_device(path.read_text(encoding="utf-8"), path.name)
        # fit the initial range to what the file maps on the chosen table, if any
        tbl = (summary or {}).get("tables", {}).get(args.table)
        if tbl:
            scanner.reconfigure(table=args.table, start=tbl["min"],
                                count=tbl["max"] - tbl["min"] + 1, max_read=args.max_read)
        print(f"loaded device file {path.name}: {summary and summary.get('model')}")
    serve(scanner, args.web_host, args.web_port, open_browser=not args.no_open)
    return 0


if __name__ == "__main__":
    sys.exit(main())
