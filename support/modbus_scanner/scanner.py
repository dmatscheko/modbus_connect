#!/usr/bin/env python3
"""Live Modbus register scanner with a small web UI — for device-file authors.

Point it at a gateway, pick a table + start address, and it rescans on an interval and shows a
packed page of registers: every known one for the plain view — dead/refused registers included as
greyed rows (write-only registers refuse reads but exist) — or the union of the selected filter
chips (served / refused / non-zero / changed / mapped / x-ray). Registers that *change*
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

# The view filter is a SET of additive atoms — the UI's toggle chips. Each selected atom adds
# its registers to the view (union; the find box still ANDs on top); no atom selected is the
# plain view: every known register, dead/refused ones included (write-only registers refuse
# reads but exist). The scan atoms (served / refused / non-zero / changed) walk the table to
# *discover* matches; every atom also contributes its already-known registers as members (see
# _filter_members), so a far match is never lost to the walk's dead-run stop — and the set
# atoms (mapped / x-ray) are members-only, which keeps far or refused mapped registers visible.
_SCAN_ATOMS = ("served", "refused", "nonzero", "changed")
_SET_ATOMS = ("mapped", "xray")
_ATOMS = (*_SCAN_ATOMS, *_SET_ATOMS)   # canonical (serialisation) order
_SCAN_SET = frozenset(_SCAN_ATOMS)
# the pre-chip single-value filters, accepted for compatibility (imports/older callers)
_LEGACY_FILTERS = {"none": (), "served": ("served",), "nonzero": ("nonzero",),
                   "changed": ("changed",), "mapped": ("mapped",), "xray": ("xray",),
                   "mappedchanged": ("mapped", "changed"), "xraychanged": ("xray", "changed")}


def _parse_filters(value: Any) -> frozenset[str]:
    """Normalise a filter selection — a list/set of atoms (the chips) or a legacy
    single-value string — into the atom set; unknown names are dropped."""
    if isinstance(value, str):
        value = _LEGACY_FILTERS.get(value, (value,))
    if not isinstance(value, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(v for v in value if v in _ATOMS)

# The find box: comma-separated terms, each an exact address ('40' / '0x28'), an address
# range ('10-20', hex ok), a case-insensitive mapping-name/key substring, or '=value' —
# matching the registers' last-known values in every reading: the raw word (incl. its int16
# view), 32/64-bit integer and float readings of adjacent registers in both word orders,
# and mapped entities' decoded values (see Scanner._value_candidates). A register matches
# when ANY term does; the whole search ANDs with the selected view filter.
_RANGE_RE = re.compile(r"(0[xX][0-9a-fA-F]+|\d+)\s*-\s*(0[xX][0-9a-fA-F]+|\d+)")
_VALUE_DEC_RE = re.compile(r"-?\d+\.\d+")   # a '=value' decimal (exponent forms are not terms)


def _parse_value_term(text: str) -> tuple[Any, ...] | None:
    """A ``=value`` find term: an exact integer (decimal, negative, or hex), or a plain
    decimal number which matches at the precision typed — ``=42.5`` matches any reading
    within 42.45..42.55, ``=42.50`` only within 42.495..42.505."""
    try:
        return ("value", int(text, 0), None)   # None = integers match exactly
    except ValueError:
        pass
    if not _VALUE_DEC_RE.fullmatch(text):
        return None
    decimals = len(text.split(".")[1])
    return ("value", float(text), 0.5 * 10 ** -decimals)   # half the last typed decimal place


def _parse_search(text: str) -> list[tuple[Any, ...]]:
    """The find box, parsed into match terms (see _RANGE_RE comment)."""
    terms: list[tuple[Any, ...]] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("="):
            term = _parse_value_term(part[1:].strip())
            if term is not None:   # an unparseable value term contributes nothing
                terms.append(term)
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
# A register that doesn't answer — refused (illegal-data-address) or, on a live link, silent —
# is only given up on (dropped from the read plan; a reconnect keeps that, Clear all or the
# row's ↻ retry re-arm it) after this many *consecutive* failures, so one spurious miss doesn't
# kill a register (a served read in between resets the count). This is the DEFAULT for the
# per-session "Give up after" setting (Scanner._dead_after), which the UI exposes.
_DEAD_AFTER_DEFAULT = 2
# Per register we keep a short history of its *distinct-from-previous* values (with the scan
# index and wall-clock time each was first seen), so after a long unattended sweep the UI can
# show how a value moved. Capped per cell; a compact tail rides along in each row for the tooltip.
HISTORY_MAX = 50
HISTORY_SPARK = 20


# --- read backends ------------------------------------------------------------
# A reader answers one block read: (values, error, illegal). ``values`` is None on
# failure; ``illegal`` is True only when the device explicitly refused the address
# (vs. a timeout), which is what marks a register genuinely "not served". ``no_device``
# is True when the failure suggests nothing lives behind the device ID at all — total
# silence, or a gateway target-failed exception — which the connect-time probe turns
# into a wrong-Device-ID warning (a gateway accepts the TCP connection for ANY ID).
@dataclass(frozen=True)
class ReadResult:
    values: list[int] | None
    error: str | None = None
    illegal: bool = False
    no_device: bool = False


# How many *consecutive* silent blocks (timeouts) end a multi-block read early, so a quiet
# device never hangs a whole page tick waiting on timeout after timeout.
_SILENT_BAIL = 3
# How many extra times a *bare timeout* (not a refusal) is retried before it counts as silent.
# A slow device may just need another go, and a timed-out request can leave a late reply that
# trips the NEXT read (transaction-id desync) — the retry drains it. Paging past a fresh region
# on a slow gateway relies on this: the first touch often times out, the retry answers.
_SLOW_RETRIES = 2
# Some devices express an unsupported register by NOT answering (a timeout) instead of a proper
# illegal-data-address exception, so a block spanning it times out whole. When the device is
# otherwise known alive, such a block is bisected register-by-register (like a refused one) to
# isolate the dead address(es) so later block reads skip them — but that costs one timeout per
# probed register, so it is capped per operation (an offline device must not bisect forever).
_MAX_SILENT_PROBES = 16


@dataclass
class ReadReport:
    """The aggregate outcome of ONE read operation (a page fill or a refresh, across all its
    block reads): how many registers actually answered — data, or an explicit refusal, both
    proving the device is alive — and how many blocks stayed silent, with the last transport
    error. Every caller derives its decision from this single result — the connection banner,
    whether paging may continue, the per-page error — so a value and a 'no answer' can never
    contradict each other (the old bug was two separate channels: recorded values on one side,
    a threshold-triggered error string on the other)."""
    answered: int = 0
    silent: int = 0
    error: str | None = None

    @property
    def alive(self) -> bool:
        """The device responded to something — it is there and talking (so any warning that
        it is absent is disproved)."""
        return self.answered > 0

    @property
    def total_failure(self) -> bool:
        """A read was attempted and nothing at all answered — total silence."""
        return self.answered == 0 and self.silent > 0

    def fold(self, other: ReadReport) -> None:
        """Accumulate a block-read's outcome into this operation-level report."""
        self.answered += other.answered
        self.silent += other.silent
        if other.error:
            self.error = other.error


Reader = Callable[[str, int, int], ReadResult]


def pymodbus_reader(
    host: str, port: int, device_id: int, timeout: float, retries: int
) -> tuple[Reader, Callable[[], bool], Callable[[], None]]:
    """A synchronous pymodbus TCP reader plus connect()/close()."""
    from pymodbus.client import ModbusTcpClient
    from pymodbus.exceptions import ModbusException, ModbusIOException
    from pymodbus.pdu import ExceptionResponse

    client = ModbusTcpClient(host, port=port, timeout=timeout, retries=retries)
    funcs = {
        "holding": client.read_holding_registers,
        "input": client.read_input_registers,
        "coil": client.read_coils,
        "discrete": client.read_discrete_inputs,
    }
    # gateway exceptions saying "nothing answered behind the requested device ID"
    gateway_dead = {10: "gateway path unavailable", 11: "gateway target device failed to respond"}

    def read(table: str, address: int, count: int) -> ReadResult:
        try:
            rr = funcs[table](address=address, count=count, device_id=device_id)
        except ModbusIOException:   # forwarded into the void — nothing answered in time
            return ReadResult(None, f"no answer from device ID {device_id}", no_device=True)
        except ModbusException as exc:
            return ReadResult(None, str(exc))
        if rr.isError():
            code = rr.exception_code if isinstance(rr, ExceptionResponse) else None
            if code in gateway_dead:
                return ReadResult(None, f"no device at ID {device_id} "
                                        f"({gateway_dead[code]}, exception {code})", no_device=True)
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


def _parse_override(spec: dict[str, Any]) -> EntityDef:
    """Validate the Details-view decode override's entity spec through the real schema and
    return its parsed EntityDef — a throwaway single-entity document, so the override never
    touches the mapping. It decodes one register at a time (whichever the Details view
    shows), so multi-word types are refused."""
    doc = {"device": {"manufacturer": "override", "model": "override"},
           "holding": {"override": {**spec, "address": 0}}}
    defn = parse_device(doc, "override.yaml").entities[0]
    if defn.span.end - defn.span.start != 1:
        raise DeviceSchemaError(
            "the override decodes one register at a time — a multi-word type cannot be "
            "decoded from a single register's words")
    return defn


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
                                           "timeout": 2.0, "retries": _DEAD_AFTER_DEFAULT}
        # "Give up after": how many consecutive failed reads before a non-responding register is
        # put on the dead list and skipped. Set from the connection's ``retries`` field (kept
        # under that key so exports/refreshes round-trip); pymodbus's own per-request retry is
        # left at 0 — the scanner retries transient timeouts itself (see _read_retry).
        self._dead_after = _DEAD_AFTER_DEFAULT
        self.table = table
        self.start, self.count = _clamp_range(start, count)
        self.max_read = _clamp_max_read(table, max_read)
        self.filter: frozenset[str] = frozenset()   # the selected filter atoms (the UI's chips) —
        # each adds its registers to the view; empty = the plain view, every known register
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
        # THE Details-view decode override (the "Decode as…" button): one global single-word
        # spec — every word-table register shown in the Details tab decodes through it (bit
        # tables read 0/1 and are left alone) until it is unmapped. The raw spec
        # exports/imports; the parsed def is its decode-ready twin.
        self.override: dict[str, Any] | None = None
        self._override_def: EntityDef | None = None
        self._starts: dict[tuple[str, int], EntityDef] = {}   # entity's first address
        self._covered: dict[tuple[str, int], EntityDef] = {}  # every address any entity occupies
        # The current filtered page: its matched addresses, and where paging continues in
        # each direction (None once that direction is exhausted at the table/map edge).
        self._page_addrs: list[int] = []
        self._page_next_anchor: int | None = None
        self._page_prev_anchor: int | None = None
        # Read-outcome bookkeeping (see ReadReport): _report accumulates the current
        # operation's reads (every _read_spans folds into it) and _settle_errors turns it
        # into the banner.
        self._report = ReadReport()
        # Single-register probes done this operation: a refused (or silent, on a known-alive
        # device) block is bisected register by register to pin down the dead address(es) (see
        # _bisect), a big slowdown the header reports as "N single probes". _op_silent_probes
        # counts just the *timeout* probes (capped at _MAX_SILENT_PROBES per op); _device_seen
        # records that this session has had a real answer, the gate for bisecting a silent block
        # (an offline device — never yet answered — must not bisect at all).
        self._op_singles = 0
        self._op_silent_probes = 0
        self._device_seen = False
        # Whether the device has answered *this operation* — set the moment any read returns
        # data, reset per op. A silent register is only given up on (struck toward the dead
        # list) when this is True: the device is provably responsive right now, so its silence
        # is a real hole, not the whole link being briefly down (which must stay retryable).
        self._op_alive = False
        # Registers given up this operation, and a live human-readable status set while a slow
        # bisection is running — read LOCK-FREE by /api/progress (a plain string, only ever
        # reassigned) so the UI can show it *during* the blocking read, then cleared when the
        # operation settles.
        self._op_dead_found = 0
        self._progress: str | None = None

    def connect(self, *, mode: str = "tcp", host: str = "", port: int = 502, device_id: int = 1,
                timeout: float = 2.0, retries: int = _DEAD_AFTER_DEFAULT) -> None:
        """(Re)open the connection from UI/CLI settings. Everything the session has gathered —
        every table's per-register stats and value history, the mapping, and the given-up-on
        (dead) register list — is **kept**, so importing a project and then connecting to watch
        it live never costs you your work; only **Clear all** (``clear_all``) wipes that.
        ``demo`` uses the simulated device; ``tcp`` connects to a gateway — and then sends one
        probe read, because a Modbus gateway accepts the TCP connection for ANY device ID: only
        a read reveals whether something answers behind it (see _probe_device). ``retries`` is
        the "Give up after" setting — failed reads before a register is given up on — NOT a
        pymodbus per-request retry (that stays 0; the scanner retries transient timeouts itself).
        Connection errors are stored (``conn_error``) and surfaced in the UI, not raised."""
        self._teardown()
        self._op_singles, self._op_silent_probes = 0, 0  # stale counts must not linger
        self._device_seen = False                        # earn it afresh on this connection
        self._dead_after = max(1, int(retries))          # 1..N failed reads before giving up
        self.connection = {"mode": mode, "host": host, "port": int(port),
                           "device_id": int(device_id), "timeout": float(timeout), "retries": int(retries)}
        if mode == "demo":
            self._read, self.connected, self.conn_error = demo_reader(), True, None
        elif not host:
            self.connected, self.conn_error = False, "host is required"
        else:
            read, do_connect, close = pymodbus_reader(
                host, int(port), int(device_id), float(timeout), 0)  # pymodbus retry off
            if do_connect():
                self._read, self._close, self.connected = read, close, True
                self.conn_error = self._probe_device()
            else:
                self.connected, self.conn_error = False, f"cannot connect to {host}:{port}"
        self.last_error = None
        self._clear_page()  # refill the view from the current inputs; the stats behind it survive

    def _probe_device(self) -> str | None:
        """One tiny read right after connecting, to catch the classic gateway trap: the TCP
        connect succeeds no matter the Device ID, and only a read reveals whether a device
        answers behind it. ANY answer — data, or a Modbus exception such as 'illegal data
        address' — proves a device is there; silence or a gateway target-failed exception
        earns a warning (not a refusal — the ID may be wrong, or the device just offline).
        Slow serial sides often miss the very first read, so silence gets one retry; and the
        warning self-heals — any later real answer clears it (see _record / _settle_errors)."""
        if self._read is None:
            return None
        result = self._read("holding", 0, 1)
        if result.no_device:
            result = self._read("holding", 0, 1)
        if not result.no_device:
            self._device_seen = True   # it answered (data or a refusal) — the device is there
            return None
        return (f"{result.error} — check the Device ID (the gateway accepts the connection "
                f"either way); this clears itself once the device answers")

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
                    filter_mode: Any = None, page_size: int | None = None,
                    search: str | None = None) -> None:
        # Keep the per-(table, address) memory so switching table/range and coming back
        # still shows the last values (and marks what changed meanwhile). Clamp the range
        # into the address space so an oversized request can't drive scans past the last register.
        # ``filter_mode`` is the atom selection — a list of chips, a legacy single-value
        # string, or None to keep the current one.
        start, count = _clamp_range(start, count)
        new_filter = self.filter if filter_mode is None else _parse_filters(filter_mode)
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

    def _begin_op(self) -> None:
        """Reset the per-operation read bookkeeping before a scan / page (see the fields)."""
        self._report = ReadReport()
        self._op_singles = self._op_silent_probes = self._op_dead_found = 0
        self._op_alive = False
        self._progress = None

    def scan(self) -> None:
        """One tick: re-read the current page's registers (membership unchanged) so a live scan
        keeps their values fresh; the first tick fills the page. Every view is a packed page —
        every known register for the plain view (dead ones included), or the union of the
        selected filter atoms (served / refused / non-zero / changed / mapped / x-ray)."""
        if not self.connected or self._read is None:
            self.last_error = "not connected"
            return
        self.last_error = None
        self._begin_op()
        self.scan_index += 1
        if self._page_addrs:
            self.refresh_page()
        else:
            self._fill_page(forward=True, anchor=self.start)  # establish the page on the first tick
        self._settle_errors()

    def _read_range(self, start: int, count: int) -> ReadReport:
        """Read & record [start, start+count) on the current table, planned so already-refused
        addresses (in _bad) are skipped. Returns the aggregate ReadReport."""
        addrs = [a for a in range(start, start + count) if (self.table, a) not in self._bad]
        return self._read_spans({Span(self.table, a, 1) for a in addrs})

    def _read_retry(self, start: int, count: int) -> ReadResult:
        """One block read on the current table, retried on a *bare timeout* (see _SLOW_RETRIES):
        a slow device may just need another go, and a timed-out request can leave a late reply
        that trips the next read (transaction-id desync) — the retry drains it. Data or an
        explicit refusal answers at once; only silence is retried."""
        result = self._read(self.table, start, count)
        tries = _SLOW_RETRIES
        while result.values is None and not result.illegal and tries > 0:
            result = self._read(self.table, start, count)
            tries -= 1
        return result

    def _read_spans(self, spans: set[Span]) -> ReadReport:
        """Read & record a set of single-address spans, planned into efficient blocks; a
        block the device refuses is bisected to the individual refused address(es). Returns
        a ReadReport (data/refusals answered vs silent blocks) and folds it into the current
        operation's report. Bails after _SILENT_BAIL consecutive silent blocks so a quiet
        device never hangs the tick — but a silent block is a NON-answer, never mistaken for
        an absent register: that distinction is what the callers act on."""
        read = self._read
        report = ReadReport()
        if read is not None:
            streak = 0
            for block in plan_blocks(spans, max_read=self.max_read, holes=self._bad):
                result = self._read_retry(block.start, block.count)
                if result.values is not None:
                    for i, addr in enumerate(range(block.start, block.end)):
                        self._record(self.table, addr, value=result.values[i])
                    report.answered += block.count
                    streak = 0
                elif result.illegal:
                    self._bisect(block, report)  # a refusal is an answer — the device is alive
                    streak = 0
                elif self._device_seen and self._op_silent_probes < _MAX_SILENT_PROBES:
                    # a timeout, but the device has answered before: this block may just span a
                    # register the device serves by NOT answering — bisect it to isolate the hole
                    # so later reads skip it (some devices time out instead of refusing).
                    self._bisect(block, report)
                    streak = 0
                else:
                    report.silent += 1  # UNRESOLVED silence: not-yet-seen, offline, or budget spent
                    report.error = result.error or "no answer"
                    streak += 1
                    if streak >= _SILENT_BAIL:
                        break
        self._report.fold(report)
        return report

    def refresh_page(self) -> None:
        """Re-read the registers of the current filtered page (its membership unchanged),
        so a live scan keeps their values fresh without reshuffling what's shown. The read
        outcome folds into the operation report; _settle_errors turns it into the banner."""
        spans: set[Span] = set()
        for addr in self._page_addrs:
            spans |= {Span(self.table, a, 1) for a in self._row_read_addrs(addr)
                      if (self.table, a) not in self._bad}
        if spans:
            self._read_spans(spans)

    def _bisect(self, block: Span, report: ReadReport) -> None:
        """Read each address of a refused-or-silent block alone to pin down the culprit(s) —
        the register-by-register fallback the header counts (see _op_singles). A register is
        given up on (a strike toward the dead list, ``_dead_after`` strikes to seal it, so a
        spurious one can't kill it) when it *refuses*, or when it *times out while the device
        is answering other registers this op* (``_op_alive`` — some devices serve an unsupported
        register by silence, not a refusal; a good neighbour proves the link is up, so this
        silence is a real hole). A timeout while nothing has answered this op is left soft and
        the block reported unresolved-silent, so a link that is merely down stays retryable and
        no register is wrongly buried. Data answers at once. Single reads (no per-read retry):
        the block already spent its retries above."""
        self._op_singles += block.count
        unresolved = False
        for addr in range(block.start, block.end):
            # a live status the UI polls (lock-free) so a slow bisection isn't a silent freeze
            self._progress = (f"Isolating unreadable registers on {self.table} — probing #{addr}"
                              f" ({self._op_dead_found} given up so far)…")
            r = self._read(self.table, addr, 1)
            key = (self.table, addr)
            if r.values is not None:
                self._record(self.table, addr, value=r.values[0])
                report.answered += 1
            elif r.illegal:
                self._strike_dead(key, addr)
                report.answered += 1   # a refusal is an answer — the device spoke
            elif self._op_alive:
                self._strike_dead(key, addr)   # silence on a live link -> a real hole, given up on
                self._op_silent_probes += 1
            else:
                # nothing has answered this op: the whole link may just be down -> keep it soft
                # and retryable, never buried on the strength of silence alone
                self._misses.pop(key, None)
                self._record(self.table, addr, error=r.error or "no answer")
                self._op_silent_probes += 1
                unresolved = True
        if unresolved:
            report.silent += 1
            report.error = "no answer"

    def _strike_dead(self, key: tuple[str, int], addr: int) -> None:
        """One strike toward the dead list for a register that refused or (on a live link) went
        silent; seal it into ``_bad`` at ``_dead_after`` strikes (the "Give up after" setting).
        Recorded "not served" — the persistence contract the dead list rebuilds from (re-armable
        via the row's ↻ / Clear all)."""
        self._misses[key] = self._misses.get(key, 0) + 1
        if self._misses[key] >= self._dead_after:
            self._bad.add(key)
        self._record(self.table, addr, error="not served", illegal=True)
        self._op_dead_found += 1

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
        if value is not None or illegal:
            # a real response (data, or an explicit refusal) proves the device is answering,
            # which disproves and clears the connect probe's "no device" warning
            self.conn_error = None
        if value is not None:
            self._device_seen = True   # a data answer — the gate for bisecting a silent block
            self._op_alive = True      # ...and (this op) the gate for striking a silent register dead
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
    def page(self, *, forward: bool, anchor: int, firm: bool = False) -> None:
        """Fill a page from ``anchor`` in one direction, scanning as far as needed to collect
        page_size matches (or reach the table/map edge). Finding nothing that way keeps the current
        page and just marks that direction exhausted (no empty page). Offline it still fills from the
        remembered cells (with no fresh reads), so an imported project can be reviewed unconnected.
        ``firm`` anchors the top of the page AT ``anchor`` (no sliding the other way to fill): the
        deliberate 'jump here' of open_page, so setting Start leaps over an unreadable stretch below
        instead of the fill sliding back down into it."""
        self.last_error = None
        self._begin_op()
        if self.connected and self._read is not None:
            self.scan_index += 1
        else:
            self.last_error = "not connected"
        self._fill_page(forward, anchor, firm)
        self._settle_errors()

    def _fill_page(self, forward: bool, anchor: int, firm: bool = False) -> None:
        matched, nxt, prv = self._collect_page(forward, anchor, firm)
        if matched:
            # got a page (even if some reads were slow) -> show it and its anchors
            self._page_addrs, self._page_next_anchor, self._page_prev_anchor = matched, nxt, prv
        elif self._report.total_failure:
            # the fill could not LOOK (every read stayed silent) — that is NOT "no more
            # registers": keep the current page AND its paging anchors, so ▶ / ◀ simply retry
            # once the device answers, instead of latching "at the end" and going dead.
            pass
        elif forward:
            self._page_next_anchor = None
        else:
            self._page_prev_anchor = None

    def _settle_errors(self) -> None:
        """Turn the operation's aggregate read report into the two banner fields, so the value
        the user sees and the warning can never disagree. Any real answer clears the connect
        probe's 'no device' warning (self-heal). A totally silent operation names the failure;
        one that answered but also hit silence is a *slow* link, not a dead one; one where
        everything answered clears the banner. An operation that read nothing (offline) leaves
        whatever was set (e.g. 'not connected')."""
        self._progress = None   # the operation's reads are done — no bisection in flight
        r = self._report
        if r.alive:
            self.conn_error = None
        if not r.answered and not r.silent:
            return
        if r.total_failure:
            self.last_error = r.error or "no answer"
        elif r.silent:
            self.last_error = ("slow link — some reads timed out, but the device is answering "
                               "(raise Timeout if this persists)")
        else:
            self.last_error = None

    def open_page(self) -> None:
        """Fill the page from the current start, falling back to the first page if nothing shows
        there (nothing served/matched at or past start). Used on every view load (/api/config) and
        when restoring a view (import): a table switch or a saved scroll position must never strand
        the view in empty space with no way to page back."""
        self._clear_page()
        self.page(forward=True, anchor=self.start, firm=True)
        if not self._page_addrs and self.start > 0:
            self.start = 0
            self.page(forward=True, anchor=0, firm=True)

    def _walking(self) -> bool:
        """Whether the page fill scans the address space to *discover* matches: the plain
        view (no atom selected) always walks, and so does any selected scan atom. The set
        atoms (mapped / x-ray) are members-only — their registers are known without probing."""
        return not self.filter or bool(self.filter & _SCAN_SET)

    def _scan_match(self, addr: int) -> bool:
        """Does this (already recorded) register match the plain view (anything known) or
        any selected scan atom? The set atoms are handled as members, not here."""
        cell = self.cells.get((self.table, addr))
        served = cell is not None and cell.error is None
        known = cell is not None or (self.table, addr) in self._bad
        f = self.filter
        if not f:  # plain view: everything known, dead/refused rows included
            return known
        return (("served" in f and served)
                or ("refused" in f and known and not served)
                or ("nonzero" in f and served and cell.value != 0)
                or ("changed" in f and served and bool(cell.changes)))

    def _scan_run(self, forward: bool, anchor: int, limit: int) -> list[int]:
        """Scan in one direction from ``anchor``, returning up to ``limit`` addresses matching
        the selected scan atoms (see _scan_match), sorted ascending. Stops at the table edge,
        a long unmatched run, or the fill cap. The unmatched-run stop counts addresses with no
        evidence of device presence — anything *known* keeps a plain / refused-listing walk
        alive, anything *served* the other filtered walks — so a served-but-zero stretch never
        ends a non-zero walk, while a genuinely mapped-out area does. An UNREADABLE (silent)
        block is decisively NOT an absent one: it stops the walk, and the caller keeps the page
        and its anchors (via _report.total_failure) so paging retries rather than latching the end.

        In the *plain* view every register is a match, so the read is sized to how many are
        still wanted (never the whole ``max_read`` when only a few remain): a Count of 3 reads 3 —
        it must not blast a full 64-wide block (and bisect it) past the requested range. The
        filtered views stay wide: their matches are sparse, so a full block is the efficient way
        to scan for them."""
        walk_known = not self.filter or "refused" in self.filter
        matched: list[int] = []
        pos, dead, scanned = anchor, 0, 0
        while len(matched) < limit and scanned < _FILTER_FILL_CAP:
            if (forward and pos > 0xFFFF) or (not forward and pos < 0):
                break
            cap = min(self.max_read, limit - len(matched)) if not self.filter else self.max_read
            count = min(cap, 0x10000 - pos) if forward else min(cap, pos + 1)
            start = pos if forward else pos - count + 1
            if self._read_range(start, count).silent:
                break   # could not read here — stop; the caller keeps a retryable anchor
            scanned += count
            block = range(start, start + count) if forward else reversed(range(start, start + count))
            for a in block:
                cell = self.cells.get((self.table, a))
                known = cell is not None or (self.table, a) in self._bad
                served = cell is not None and cell.error is None
                if not (known if walk_known else served):
                    dead += 1
                    continue
                dead = 0
                if not self._scan_match(a):
                    continue
                matched.append(a)
                if len(matched) >= limit:
                    break
            pos = start + count if forward else start - 1
            if dead >= _FILTER_DEAD_RUN:  # a long refused run — the device's map ended here
                break
        matched.sort()
        return matched

    def _value_candidates(self, number: int | float, tol: float | None) -> set[int]:
        """Addresses whose *last-known* values match a ``=value`` find term, on the current
        table — no probing, the remembered cells are searched. Every reading is checked
        against the number: the raw word (and its int16 view), the 32/64-bit integer and
        float readings of adjacent registers (both word orders, matched at their start
        address), and the mapping's / overlays' entities whose decoded value is numeric.
        Integers must match exactly; decimals match at the precision typed (``tol`` is
        half their last decimal place)."""
        def hits(x: int | float) -> bool:
            if isinstance(x, float) and not math.isfinite(x):
                return False
            return x == number if tol is None else abs(x - number) <= tol
        vals = {a: c.value for (t, a), c in self.cells.items()
                if t == self.table and c.value is not None}
        out = {a for a, v in vals.items() if hits(v)}
        if self.table not in BIT_TABLES:
            for a, v in vals.items():
                if v >= 0x8000 and hits(v - 0x10000):   # the word's int16 reading
                    out.add(a)
            for a in vals:   # multi-word readings, both word orders, matched at the start
                if a in out:
                    continue
                for count, ffmt in ((2, ">f"), (4, ">d")):
                    words = [vals.get(a + i) for i in range(count)]
                    if None in words:
                        continue
                    for order in (words, list(reversed(words))):
                        raw = struct.pack(f">{count}H", *order)
                        if (hits(int.from_bytes(raw, "big"))
                                or hits(int.from_bytes(raw, "big", signed=True))
                                or hits(struct.unpack(ffmt, raw)[0])):
                            out.add(a)
                            break
                    if a in out:
                        break
        for index in [self._starts, *(ov.starts for ov in self.additional)]:
            for (t, a), defn in index.items():
                if t != self.table or a in out:
                    continue
                decoded, err = self._decode_entity(defn)
                if (err is None and isinstance(decoded, (int, float))
                        and not isinstance(decoded, bool) and hits(decoded)):
                    out.add(a)
        return out

    def _search_candidates(self) -> list[int]:
        """Every address the active search could match — computable outright, no scanning:
        address and range terms name their addresses; name terms contribute the covered
        addresses (every table's with the x-ray atom on, else this table's) whose entity
        name/key contains the term; value terms the addresses whose remembered values
        match (see _value_candidates). The search fill probes only these candidates, so
        a fresh session finds a far register as fast as an already-scanned one."""
        out: set[int] = set()
        tables = TABLES if "xray" in self.filter else (self.table,)
        indexes = [self._covered] + [ov.covered for ov in self.additional]
        for term in self._search_terms:
            if term[0] == "addr":
                if 0 <= term[1] <= 0xFFFF:
                    out.add(term[1])
            elif term[0] == "range":
                out.update(range(max(0, term[1]), min(term[2], 0xFFFF) + 1))
            elif term[0] == "value":
                out |= self._value_candidates(term[1], term[2])
            else:
                for index in indexes:
                    for (t, a), defn in index.items():
                        if t in tables and (term[1] in (defn.ha.get("name") or "").casefold()
                                            or term[1] in defn.key.casefold()):
                            out.add(a)
        return sorted(out)

    def _covered_here(self, addr: int) -> bool:
        """Any layer (the mapping or an additive overlay) covers this current-table address."""
        return ((self.table, addr) in self._covered
                or any((self.table, addr) in ov.covered for ov in self.additional))

    def _covered_anywhere(self, addr: int) -> bool:
        """Any layer covers this address on *any* table — the x-ray atom's membership."""
        return (any((t, addr) in self._covered for t in TABLES)
                or any((t, addr) in ov.covered for ov in self.additional for t in TABLES))

    def _row_shows(self, addr: int) -> bool:
        """Whether the current view lists this (already probed) register — the walk's
        predicate restated for the candidate-driven search fill, extended with the set
        atoms' membership. The plain view also counts a *mapped* register as known even
        with no cell behind it (an imported project may carry the mapping but not that
        register's reads; offline, a name match must still show its row)."""
        if not self.filter:
            return (self.cells.get((self.table, addr)) is not None
                    or (self.table, addr) in self._bad or self._covered_here(addr))
        return (self._scan_match(addr)
                or ("mapped" in self.filter and self._covered_here(addr))
                or ("xray" in self.filter and self._covered_anywhere(addr)))

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
        of walking the address space (each candidate is probed and kept if any selected
        atom shows it — _row_shows), then top up the other way when short at an edge,
        like the scanned fills do."""
        cands = self._search_candidates()
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
        """Every selected atom's already-KNOWN current-table addresses — the page fill
        unions these with the walk's discoveries (see _collect_page), so a far match (a
        mapped register beyond a dead run, a changed one seen long ago) is never lost to
        the walk's stop conditions. ``mapped`` contributes every address any layer's
        entity occupies, ``xray`` every table's, projected onto this table; the scan
        atoms contribute their matching recorded cells. The plain view (no atom) needs
        no members — its walk lists everything known as it goes."""
        f = self.filter
        members: set[int] = set()
        if "mapped" in f or "xray" in f:
            table = None if "xray" in f else self.table   # None = every table's addresses
            for index in [self._covered, *(ov.covered for ov in self.additional)]:
                members.update(a for (t, a) in index if table is None or t == table)
        if f & _SCAN_SET:
            for (t, a), cell in self.cells.items():
                if t != self.table:
                    continue
                served = cell.error is None
                if (("served" in f and served)
                        or ("refused" in f and not served)
                        or ("nonzero" in f and served and cell.value != 0)
                        or ("changed" in f and served and cell.changes)):
                    members.add(a)
            if "refused" in f:  # known dead from a device file's hint — never probed, no cell
                members.update(a for (t, a) in self._bad if t == self.table)
        return members

    def _row_read_addrs(self, addr: int) -> set[int]:
        """The current-table addresses to read for one page row. With the mapped / x-ray
        atoms on, a covered register expands to its entity's whole span (so split entities
        still decode); x-ray also expands a sibling-table entity's span, since that entity
        is decoded against *this* table's registers — both for the editable mapping and for
        every additive overlay. Everything else is just the address."""
        out = {addr}
        if "mapped" in self.filter or "xray" in self.filter:
            indexes = [self._covered] + [ov.covered for ov in self.additional]
            for index in indexes:
                defns = [index.get((self.table, addr))]
                if "xray" in self.filter:
                    defns.append(index.get((_SIBLING[self.table], addr)))
                for defn in defns:
                    if defn is not None:
                        out.update(range(defn.span.start, defn.span.end))
        return out

    def _collect_page(self, forward: bool, anchor: int,
                      firm: bool = False) -> tuple[list[int], int | None, int | None]:
        """Collect a full window of page_size registers around ``anchor`` and return (page,
        next_anchor, prev_anchor). Every page is filled to page_size when that many registers
        exist: it collects the paging direction, and if it comes up short at an edge it slides
        the window the other way to top it up — so paging never leaves a half-empty screen —
        UNLESS ``firm`` (a jump to ``anchor``): then a short page stays short rather than sliding
        back below the anchor, so setting Start leaps over an unreadable stretch instead of the
        fill reading down into it.
        The page is the union of two sources: a scanning walk that *discovers* matches (the
        plain view and the scan atoms — see _scan_run) and the selected atoms' already-known
        members (see _filter_members), read afterwards so unprobed mapped registers and split
        entity spans decode. The anchors are the next / previous register just beyond the page
        from either source (None at the true ends, so ▶ / ◀ disable there)."""
        want = max(1, self.page_size)
        if self._search_terms:  # the find box ANDs with the view filter (candidate-driven)
            return self._collect_search_page(forward, anchor, want)
        members = sorted(self._filter_members())
        walking = self._walking()
        walked: set[int] = set()

        def run(fwd: bool, from_: int, need: int) -> list[int]:
            """One direction's matches: walk discoveries unioned with the known members."""
            got: set[int] = set()
            if walking:
                found = self._scan_run(fwd, from_, need)
                walked.update(found)
                got.update(found)
            if fwd:
                got.update(a for a in members if a >= from_)
                return sorted(got)[:need]
            got.update(a for a in members if a <= from_)
            return sorted(got)[-need:]

        page = run(forward, anchor, want)
        if not page and not walking and members and not firm:
            # a members-only view with nothing in the paging direction slides to the far
            # window (e.g. a table switch landing past everything mapped), never an empty page
            page = members[-want:] if forward else members[:want]
        if 0 < len(page) < want and not firm:  # short at an edge: slide the other way to fill
            if forward:
                page = sorted(set(run(False, page[0] - 1, want - len(page))) | set(page))
            else:
                page = sorted(set(page) | set(run(True, page[-1] + 1, want - len(page))))
        if not page:
            return [], None, None
        # read the rows the walk didn't just read — member rows (probing unprobed mapped
        # registers) and their entity spans — skipping known-dead addresses
        spans = {Span(self.table, x, 1) for a in page if a not in walked
                 for x in self._row_read_addrs(a) if (self.table, x) not in self._bad}
        if spans:
            self._read_spans(spans)
        # Anchors = where ▶ / ◀ continue. The members-based views (mapped / x-ray) window over a
        # known set, so their edges ARE the member edges. A *walking* view (plain / scan atoms)
        # has no fixed end, so it enables paging purely by the address-space bounds — no probe
        # past the page: ▶ is live while the last shown register is below the top of the space,
        # ◀ while the first is above 0, and the click itself walks on from there. (This replaces
        # a one-register look-ahead read that, on a slow/dead edge, cost a timeout per page.)
        nxt = min((a for a in members if a > page[-1]), default=None)
        prv = max((a for a in members if a < page[0]), default=None)
        if walking:
            if nxt is None and page[-1] < 0xFFFF:
                nxt = page[-1] + 1
            if prv is None and page[0] > 0:
                prv = page[0] - 1
        return page, nxt, prv

    # --- serialisation -------------------------------------------------------
    def config(self) -> dict[str, Any]:
        return {"table": self.table, "start": self.start, "count": self.count,
                "max_read": self.max_read, "search": self.search,
                "filter": [a for a in _ATOMS if a in self.filter]}  # chips, canonical order

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
            if "xray" in self.filter:
                self._xray_overlay(row, addr)
        if self.additional:
            self._additional_overlay(row, addr)
        return row

    def history(self, table: str, address: int) -> dict[str, Any]:
        """The full recorded history for one register — its distinct-from-previous values with
        the scan index and timestamp each was first seen — for the side panel. The value only
        grows history when the register is actually read (i.e. its page is scanned). When the
        register decodes *on its own* — the global Details-view "decode as" override (wins,
        on any word-table register), or a mapped entity that starts here and spans just this
        register — every entry also carries ``decoded`` and ``decode`` names the source, so
        the UI can turn the value column into a decoded one; a multi-word entity cannot
        decode from one register's history."""
        cell = self.cells.get((table, address))
        entity: dict[str, Any] | None = None
        if self.device is not None:
            defn = self._starts.get((table, address)) or self._covered.get((table, address))
            if defn is not None:
                entity = {"name": defn.ha.get("name") or defn.key, "address": defn.address}
        entries = [dict(h) for h in cell.history] if cell is not None else []
        decode: dict[str, Any] | None = None
        dec_defn = None
        if self._override_def is not None and table not in BIT_TABLES:
            dec_defn, decode = self._override_def, {"source": "override"}
        else:
            start = self._starts.get((table, address))
            if start is not None and start.span.end - start.span.start == 1:
                dec_defn = start
                # the raw spec rides along so the UI can label the column with its type
                # (e.g. "uint16 x0.1") exactly as it does for the override
                decode = {"source": "entity", "name": start.ha.get("name") or start.key,
                          "spec": (self.map_doc or {}).get(start.table, {}).get(start.key)}
        if dec_defn is not None:
            for e in entries:
                raw = [bool(e["value"])] if table in BIT_TABLES else [e["value"]]
                try:
                    e["decoded"] = _jsonable(codec.decode(dec_defn, raw))
                except Exception:
                    e["decoded"] = e["value"]  # e.g. an enum value with no label — show it raw
        return {"table": table, "address": address, "history": entries,
                "value": cell.value if cell is not None else None,
                "changes": cell.changes if cell is not None else 0, "entity": entity,
                "decode": decode, "override": self.override}

    def snapshot(self) -> dict[str, Any]:
        """The current view as rows, for rendering (see full_state for export). Every view is a
        packed page that page() fills and ◀ / ▶ walk: every known register for the plain view —
        refused/dead ones included (write-only registers refuse reads but exist) — or the union
        of the selected filter atoms (served / refused / non-zero / changed / mapped / x-ray).
        The filtered views read past dead registers so the page always fills."""
        base = {"config": self.config(), "scan_index": self.scan_index,
                "last_error": self.last_error, "single_probes": self._op_singles,
                "device": self.device_summary(),
                "meta": dict(self.meta),
                "imported": dict(self.imported["meta"]) if self.imported else None,
                "additional": [{"name": ov.name, "manufacturer": ov.device.manufacturer,
                                "model": ov.device.model} for ov in self.additional],
                "override": self.override,
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
                "override": self.override,
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
                               "timeout": float(conn.get("timeout") or 2.0),
                               "retries": int(conn.get("retries") or _DEAD_AFTER_DEFAULT)}
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
        # ...and so does the Details-view decode override, revalidated like everything else
        self.override, self._override_def = None, None
        spec = data.get("override")
        if isinstance(spec, dict):
            try:
                spec = _restore_int_keys(spec)
                self._override_def = _parse_override(spec)
                self.override = spec
            except (DeviceSchemaError, yaml.YAMLError, ValueError, KeyError, TypeError) as exc:
                self.last_error = (f"decode override could not be restored: "
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

    def set_override(self, fields: dict[str, Any]) -> None:
        """Set THE Details-view decode override — the "Decode as…" button: one global spec,
        and every word-table register shown in the Details tab decodes its value/history
        through it (instead of any mapped entity) until it is unmapped. Validated by the
        real schema; a bad spec raises and leaves the current override alone."""
        spec = _entity_from_fields("holding", {**fields, "address": 0,
                                               "platform": "sensor", "name": "override"})
        defn = _parse_override(spec)
        spec.pop("address", None)  # the override is register-independent
        self.override, self._override_def = spec, defn

    def clear_override(self) -> None:
        """Drop the Details-view decode override — values decode normally again."""
        self.override, self._override_def = None, None

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
        self.override, self._override_def = None, None
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
        ``amaps``. Without the x-ray atom only the current table's entities appear; with
        it each overlay is treated exactly like the mapping's own x-ray — its same-width
        sibling entities decoded against the *current* table's registers, its
        non-compatible tables' entities named for the hover title (``other``). The UI
        fills a still-empty cell with the first hit — grey, tagged with this register's
        own address (it maps HERE, unlike a sibling projection) — and corners the rest
        after any x-ray entries."""
        sib = _SIBLING[self.table]
        xray = "xray" in self.filter
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
    ``swap: word`` rows show a word-swapped device. Values are FULL precision (floats
    as repr) — rounding is the UI's job, display-only, never the data's."""
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
        elif self.path == "/api/progress":
            # deliberately LOCK-FREE: a scan/page holds the lock for its whole (possibly slow)
            # duration, so the only way to report progress *during* it is to read the plain
            # status string without contending — it is only ever reassigned, never mutated.
            self._json({"progress": self._scanner._progress})
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
                    retries=int(body.get("retries") or _DEAD_AFTER_DEFAULT),
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
                    filter_mode=body.get("filter"),  # a chip list or a legacy string; None keeps
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
            elif self.path == "/api/override":
                try:
                    self._scanner.set_override(body)
                except (DeviceSchemaError, yaml.YAMLError, ValueError, KeyError) as exc:
                    self._json({"error": " ".join(str(exc).split())}, 400)
                    return
                self._json(self._scanner.snapshot())
            elif self.path == "/api/unoverride":
                self._scanner.clear_override()
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
    parser.add_argument("--retries", type=int, default=_DEAD_AFTER_DEFAULT,
                        help="give up on a non-responding register after this many failed reads "
                             "(the UI's 'Give up after'); not a pymodbus per-request retry")
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
