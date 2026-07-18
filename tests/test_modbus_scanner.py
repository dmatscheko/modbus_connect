"""The standalone register scanner (support/modbus_scanner): scan bookkeeping,
learned-bad-address skipping (via the integration's planner), cross-table value
memory, the interactive mapping (add/edit/unmap, validated by the real schema),
and — most important — that the device-file it generates is valid against the schema."""

import importlib.util
import json
import struct
import sys
from pathlib import Path

import pytest
import yaml

from custom_components.modbus_connect.schema import parse_device

_ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "modbus_scanner", _ROOT / "support/modbus_scanner/scanner.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # so dataclasses can resolve the module (py3.14)
    spec.loader.exec_module(mod)
    return mod


scanner = _load()


class FakeDevice:
    """A block read fails whole if it spans a refused address — like a real device."""

    def __init__(self, values, illegal=frozenset()):
        self.values = dict(values)
        self.illegal = set(illegal)
        self.reads: list[tuple[int, int]] = []

    def read(self, table, address, count):
        self.reads.append((address, count))
        block = []
        for a in range(address, address + count):
            if a in self.illegal:
                return scanner.ReadResult(None, "exception 2", illegal=True)
            block.append(self.values.get(a, 0))
        return scanner.ReadResult(block)


def _cell(snap, addr):
    return next(r for r in snap["rows"] if r["address"] == addr)


def _state(sc, addr, table=None):
    # a cell's remembered state, regardless of whether it's on the current (packed) page
    return sc.cells[(table or sc.table, addr)]


def test_scan_tracks_changes_and_errors():
    dev = FakeDevice({0: 10, 1: 20, 2: 30}, illegal={5})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=8, max_read=4)

    sc.scan()
    snap = sc.snapshot()
    assert _cell(snap, 0)["value"] == 10
    assert _cell(snap, 0)["changes"] == 0  # first sighting is not a change
    assert _cell(snap, 0)["reads"] == 1
    assert _cell(snap, 5)["error"] == "not served"        # refused -> still a row, flagged dead
    assert _state(sc, 5).error == "not served"            # ...and its refusal is remembered

    dev.values[0] = 11
    dev.reads.clear()
    sc.scan()
    snap = sc.snapshot()
    assert _cell(snap, 0)["value"] == 11
    assert _cell(snap, 0)["changes"] == 1
    assert _cell(snap, 0)["reads"] == 2
    assert _cell(snap, 0)["last_changed"] == 2  # the second scan
    assert _cell(snap, 2)["changes"] == 0  # unchanged register stays cold


def test_plain_view_lists_dead_registers_and_served_view_packs_past_them():
    # 1 is refused: `all` lists it as a flagged row (write-only registers exist!), while the
    # packed `served` view reads past it to fill the page with what the device answers
    dev = FakeDevice({0: 1, 2: 3, 3: 4, 4: 5}, illegal={1})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=3, max_read=4)
    sc.scan()
    snap = sc.snapshot()
    assert [r["address"] for r in snap["rows"]] == [0, 1, 2]           # every register, dead 1 included
    assert _cell(snap, 1)["error"] == "not served"
    sc.reconfigure(table="holding", start=0, count=3, max_read=4, filter_mode="served", page_size=3)
    sc.page(forward=True, anchor=0)
    assert [r["address"] for r in sc.snapshot()["rows"]] == [0, 2, 3]  # skipped refused 1, filled to 3


def test_register_is_skipped_only_after_two_not_served_in_a_row():
    dev = FakeDevice({0: 10, 1: 20}, illegal={2})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=4, max_read=4)

    sc.page(forward=True, anchor=0)  # a fill reads past address 2: first "not served"
    assert _state(sc, 2).error == "not served"
    assert ("holding", 2) not in sc._bad

    dev.reads.clear()
    sc.page(forward=True, anchor=0)  # a second fill re-probes it: second "not served" in a row
    assert any(a <= 2 < a + n for a, n in dev.reads)  # it WAS re-read to earn the second strike
    assert ("holding", 2) in sc._bad

    dev.reads.clear()
    sc.page(forward=True, anchor=0)  # now a learned hole — never read again
    assert all(not (a <= 2 < a + n) for a, n in dev.reads)


def test_retry_reprobes_one_dead_register():
    dev = FakeDevice({0: 1, 2: 3}, illegal={1})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=3, max_read=4)
    sc.page(forward=True, anchor=0)
    sc.page(forward=True, anchor=0)                    # two refusals in a row -> dead
    assert ("holding", 1) in sc._bad
    assert _cell(sc.snapshot(), 1)["dead"] is True     # the row carries the flag for the ↻ button

    dev.reads.clear()
    sc.retry_address("holding", 1)                     # still refused: one probe, straight back to dead
    assert dev.reads == [(1, 1)]                       # exactly that one register, nothing else
    assert ("holding", 1) in sc._bad

    dev.illegal = set()                                # the device serves it now
    dev.values[1] = 42
    sc.retry_address("holding", 1)
    assert ("holding", 1) not in sc._bad
    snap = sc.snapshot()
    assert _cell(snap, 1)["value"] == 42 and not _cell(snap, 1).get("dead")


def test_search_narrows_any_view_by_address_and_name():
    # 0..9 served except 3 (dead after two fills); a 2-register "Heat flow" entity at 5
    dev = FakeDevice({a: a + 10 for a in range(10)}, illegal={3})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=10, max_read=16)
    sc.set_mapping("holding", 5, {"name": "Heat flow", "platform": "sensor", "type": "uint32"})
    sc.reconfigure(table="holding", start=0, count=10, max_read=16, filter_mode="none", page_size=10)
    sc.page(forward=True, anchor=0)
    sc.page(forward=True, anchor=0)                    # second refusal -> 3 dead (still listed in all)

    def rows():
        return [r["address"] for r in sc.snapshot()["rows"]]

    # comma-separated terms OR together: an exact address plus a hex range
    sc.reconfigure(table="holding", start=0, count=10, max_read=16, filter_mode="none",
                   page_size=10, search="2, 0x7-8")
    sc.open_page()
    assert rows() == [2, 7, 8]
    # a name substring matches every register its entity covers (the ↑ tail too)
    sc.reconfigure(table="holding", start=0, count=10, max_read=16, filter_mode="none",
                   page_size=10, search="heat")
    sc.open_page()
    assert rows() == [5, 6]
    # the find box ANDs with the view filter: served hides the dead 3 inside the searched range
    sc.reconfigure(table="holding", start=0, count=10, max_read=16, filter_mode="served",
                   page_size=10, search="2-4")
    sc.open_page()
    assert rows() == [2, 4]
    # and it restricts the set-based views' membership the same way
    sc.reconfigure(table="holding", start=0, count=10, max_read=16, filter_mode="mapped",
                   page_size=10, search="6")
    sc.open_page()
    assert rows() == [6]
    assert sc.snapshot()["config"]["search"] == "6"    # the UI restores the box from config


def test_search_matches_every_tables_names_in_xray_views():
    dev = FakeDevice({0: 1, 1: 2, 2: 3})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=3, max_read=4)
    sc.set_mapping("input", 1, {"name": "Volt", "platform": "sensor"})
    sc.set_mapping("coil", 0, {"name": "Pump", "platform": "binary_sensor"})  # non-compatible table
    sc.set_mapping("holding", 2, {"name": "Amps", "platform": "sensor"})

    # x-ray membership spans every table, so name terms search every table's mappings —
    # the sibling's (shown as if local) and the non-compatible ones (hover-only) alike
    sc.reconfigure(table="holding", start=0, count=3, max_read=4, filter_mode="xray",
                   page_size=4, search="volt")
    sc.open_page()
    assert [r["address"] for r in sc.snapshot()["rows"]] == [1]
    sc.reconfigure(table="holding", start=0, count=3, max_read=4, filter_mode="xray",
                   page_size=4, search="pump")
    sc.open_page()
    assert [r["address"] for r in sc.snapshot()["rows"]] == [0]
    # the mapped view lists local entities only — a foreign name finds nothing there
    sc.reconfigure(table="holding", start=0, count=3, max_read=4, filter_mode="mapped",
                   page_size=4, search="volt")
    sc.open_page()
    assert sc.snapshot()["rows"] == []


def test_search_probes_only_its_candidates_on_a_fresh_session():
    # nothing scanned yet: a name search must find a far mapped register right away by
    # probing just its registers — not walk (and bisect) the address space up to it
    dev = FakeDevice({400: 7, 401: 3})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=10, max_read=16)
    sc.set_mapping("holding", 400, {"name": "Heat pool", "platform": "sensor", "type": "uint32"})
    sc.reconfigure(table="holding", start=0, count=10, max_read=16, filter_mode="none",
                   page_size=10, search="heat")
    sc.open_page()
    assert [r["address"] for r in sc.snapshot()["rows"]] == [400, 401]
    assert dev.reads and all(a >= 400 and a + n <= 402 for a, n in dev.reads)


def test_name_search_works_offline_right_after_importing_a_project():
    # the reported flow: scan + map online, export; later import the modbus-scan.json and
    # search a name straight away — offline, before any paging or connecting
    dev = FakeDevice({5: 11, 6: 22})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=8, max_read=8)
    sc.page(forward=True, anchor=0)                    # the export carries cells for 0..7
    sc.set_mapping("holding", 5, {"name": "Heat flow", "platform": "sensor", "type": "uint32"})
    sc.set_mapping("holding", 200, {"name": "Mode", "platform": "sensor"})  # mapped, never scanned
    state = sc.full_state()

    restored = scanner.Scanner(table="holding", start=0, count=8, max_read=8)  # offline
    restored.load_state(state)
    restored.reconfigure(table="holding", start=0, count=8, max_read=8, filter_mode="none",
                         page_size=8, search="heat")
    restored.open_page()
    rows = restored.snapshot()["rows"]
    assert [r["address"] for r in rows] == [5, 6]
    assert rows[0]["entity"]["name"] == "Heat flow" and rows[0]["value"] == 11
    # a mapped register the export never scanned is still findable by name (no cell yet)
    restored.reconfigure(table="holding", start=0, count=8, max_read=8, filter_mode="none",
                         page_size=8, search="mode")
    restored.open_page()
    rows = restored.snapshot()["rows"]
    assert [r["address"] for r in rows] == [200]
    assert rows[0]["value"] is None                    # nothing read yet — but the row is there


def test_a_served_read_resets_the_not_served_streak():
    # a register that answers once between refusals must not be given up on — the two "not served"
    # have to be consecutive (drive raw reads so the count is exact, not the packed page's look-aheads)
    dev = FakeDevice({0: 1}, illegal={0})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=1, max_read=1)

    sc._read_range(0, 1)   # miss 1
    assert ("holding", 0) not in sc._bad
    dev.illegal = set()    # device serves it now
    sc._read_range(0, 1)   # a served read resets the streak
    assert _state(sc, 0).value == 1 and ("holding", 0) not in sc._bad
    dev.illegal = {0}      # refused again
    sc._read_range(0, 1)   # miss 1 (of a fresh streak), not 2
    assert ("holding", 0) not in sc._bad
    sc._read_range(0, 1)   # miss 2 in a row -> given up on
    assert ("holding", 0) in sc._bad


def test_bisect_pins_the_single_refused_address():
    dev = FakeDevice({}, illegal={6})  # only 6 is refused; its whole block still fails
    sc = scanner.Scanner(dev.read, table="input", start=0, count=8, max_read=8)
    sc.scan()
    assert _state(sc, 6).error == "not served"
    assert all(_state(sc, a).error is None for a in range(8) if a != 6)


def test_values_are_remembered_across_tables():
    # holding and input share addresses but are distinct; memory must not bleed between them
    dev = FakeDevice({0: 100, 1: 200})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=2, max_read=2)
    sc.scan()
    assert _state(sc, 0).value == 100

    sc.reconfigure(table="input", start=0, count=2, max_read=2)
    dev.values = {0: 999, 1: 0}
    sc.scan()
    assert _state(sc, 0, "input").value == 999
    assert _state(sc, 0, "holding").value == 100   # holding memory untouched by the input scan

    # back on holding, a rescan flags that its value changed while we were on the other table
    dev.values = {0: 111, 1: 200}
    sc.reconfigure(table="holding", start=0, count=2, max_read=2)
    sc.scan()
    assert _state(sc, 0).value == 111 and _state(sc, 0).changes == 1


def test_generated_device_file_is_valid():
    # 0,1,2,3 and 7 are served (7 sits past a refused register); 5 is refused and lands
    # in the gap between 3 and 7, so it must survive as a planner hint. 9 is refused too
    # but past the last mapped register, so it is dropped (the integration never reads it).
    dev = FakeDevice({0: 10, 1: 20, 2: 30, 3: 0, 7: 70}, illegal={5, 9})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=10, max_read=4)
    sc.page(forward=True, anchor=0)
    dev.values[0] = 11
    sc.page(forward=True, anchor=0)  # a second fill: addr 0 changes; refused 5 & 9 earn a 2nd strike

    text = sc.generate_yaml("Acme", "X1", [0, 1, 2, 3, 7])
    doc = yaml.safe_load(text)
    device = parse_device(doc, "generated.yaml")  # must not raise
    assert device.manufacturer == "Acme"
    assert {e.key for e in device.entities} == {f"holding_{a:04x}" for a in (0, 1, 2, 3, 7)}
    changed = next(e for e in device.entities if e.key == "holding_0000")
    assert changed.ha.get("state_class") == "measurement"  # it moved -> a measurement
    static = next(e for e in device.entities if e.key == "holding_0002")
    assert "state_class" not in static.ha
    # only the refused address *between* mapped registers is kept; 9 (past the last mapped
    # register) is dropped — writing every dead address would bloat the file for nothing
    assert doc["device"]["bad_addresses"]["holding"] == [5]


def test_generate_prunes_bad_addresses_to_one_per_gap():
    reduce = scanner._reduce_bad_addresses
    # holding reads at 0,1,10,11,20: dead 3 and 7 share the gap (1,10) -> keep only the
    # first (3); 15 is alone in gap (11,20) -> kept; 25 is past the last read -> dropped.
    # input has a single read register (5), hence no gaps, so all its dead ones go.
    reads = {"holding": {0, 1, 10, 11, 20}, "input": {5}}
    bad = {"holding": {3, 7, 15, 25}, "input": {2, 9}}
    assert reduce(reads, bad) == {"holding": [3, 15]}
    # dead registers only outside the mapped range collapse to nothing at all
    assert reduce({"holding": {10, 11, 12}}, {"holding": {5, 8, 20, 40}}) == {}
    # a dead address that is also a read register (contradictory input) is never emitted
    assert reduce({"holding": {10, 20}}, {"holding": {10, 15}}) == {"holding": [15]}


def test_full_state_roundtrips_across_tables():
    dev = FakeDevice({0: 7, 1: 8}, illegal={3})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=4, max_read=4)
    sc.scan()
    sc.reconfigure(table="input", start=0, count=2, max_read=2)
    sc.scan()
    state = sc.full_state()
    assert {c["table"] for c in state["cells"]} == {"holding", "input"}  # spans tables

    restored = scanner.Scanner(table="holding", start=0, count=4, max_read=4)
    restored.load_state(state)
    assert restored.scan_index == sc.scan_index
    assert restored.table == "holding"                 # the import doesn't move you off your table
    assert ("holding", 3) in restored._bad             # refused addresses survive an import
    # the remembered cells (across both tables) come back intact
    assert restored.cells[("holding", 0)].value == 7
    assert restored.cells[("input", 0)].value == sc.cells[("input", 0)].value


def test_table_switch_keeps_position_and_falls_back_when_nothing_is_served_there():
    # holding serves 0..59; input serves only 0..9 — the /api/config flow (reconfigure +
    # open_page) keeps the position when the switched-to view shows something there, else
    # falls back to the first page (a packed view like 'served' can come up empty)
    def read(table, address, count):
        limit = 60 if table == "holding" else 10
        if address + count > limit:
            return scanner.ReadResult(None, "exception 2", illegal=True)
        return scanner.ReadResult(list(range(address, address + count)))

    sc = scanner.Scanner(read, table="holding", start=40, count=8, max_read=8)
    sc.reconfigure(table="holding", start=40, count=8, max_read=8, filter_mode="served", page_size=8)
    sc.open_page()
    assert [r["address"] for r in sc.snapshot()["rows"]] == list(range(40, 48))   # viewing holding @40

    # switch to input at the kept position: nothing served there -> fall back to the first page
    sc.reconfigure(table="input", start=40, count=8, max_read=8, filter_mode="served", page_size=8)
    sc.open_page()
    assert [r["address"] for r in sc.snapshot()["rows"]] == list(range(8))
    assert sc.start == 0                                            # the fallback is the new position

    # back to holding at a position it serves: the view stays put
    sc.reconfigure(table="holding", start=40, count=8, max_read=8, filter_mode="served", page_size=8)
    sc.open_page()
    assert [r["address"] for r in sc.snapshot()["rows"]] == list(range(40, 48))

    # the plain view never needs the fallback: dead registers are listed, so the position
    # holds even where the switched-to table serves nothing at all
    sc.reconfigure(table="input", start=40, count=8, max_read=8, filter_mode="none", page_size=8)
    sc.open_page()
    rows = sc.snapshot()["rows"]
    assert [r["address"] for r in rows] == list(range(40, 48)) and sc.start == 40
    assert all(r["error"] for r in rows)


def test_export_restores_connection_and_tuning_but_not_the_view():
    sc = scanner.Scanner(FakeDevice({0: 1}).read, table="input", start=40, count=7, max_read=9)
    sc.reconfigure(table="input", start=40, count=7, max_read=9, filter_mode="nonzero")
    sc.connection = {"mode": "tcp", "host": "10.0.0.60", "port": 502, "device_id": 3,
                     "timeout": 1.5, "retries": 2}
    state = sc.full_state()
    assert set(state["config"]) == {"count", "max_read"}          # only the tuning, not table/start/filter
    assert state["connection"]["host"] == "10.0.0.60"

    restored = scanner.Scanner(table="holding", start=0, count=64, max_read=64)   # a different view
    restored.load_state(state)
    assert restored.count == 7 and restored.max_read == 9         # Count / Per-read restored
    assert restored.page_size == 7   # ...and Count is actually APPLIED (rows per page, every view)
    assert restored.connection["host"] == "10.0.0.60" and restored.connection["device_id"] == 3
    assert restored.connection["timeout"] == 1.5 and restored.connection["retries"] == 2
    assert restored.table == "holding" and restored.filter == frozenset()  # the view is left untouched

    filtered = scanner.Scanner(table="holding", start=0, count=64, max_read=64)
    filtered.reconfigure(table="holding", start=0, count=64, max_read=64, filter_mode="mapped")
    filtered.load_state(state)
    assert filtered.page_size == 7   # Count is the page size under a filter too


def test_export_import_round_trips_a_mapping_with_integer_map_keys():
    # JSON stringifies a mapping's integer 'map' keys; import must restore them (else the whole
    # mapping fails to parse and is silently lost — a saved project must reload with its mapping)
    dev = FakeDevice({0: 1, 1: 2})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=2, max_read=2)
    sc.set_mapping("holding", 0, {"name": "Mode", "platform": "select", "map": "0: Off, 1: On, 2: Auto"})
    sc.scan()
    assert sc.device is not None and len(sc.device.entities) == 1

    exported = json.loads(json.dumps(sc.full_state()))   # exactly what the UI export/import does
    restored = scanner.Scanner(table="holding", start=0, count=2, max_read=2)
    restored.load_state(exported)

    assert restored.device is not None                   # the mapping came back, not silently dropped
    assert restored.map_doc["holding"]["holding_0000"]["map"] == {0: "Off", 1: "On", 2: "Auto"}
    assert restored.last_error is None


def test_import_of_a_malformed_project_raises_and_keeps_the_session():
    # /api/import turns the raised error into a 400; the session must survive intact —
    # load_state parses the whole file before it replaces anything
    dev = FakeDevice({0: 7})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=2, max_read=2)
    sc.scan()
    assert sc.cells[("holding", 0)].value == 7
    with pytest.raises(KeyError):
        sc.load_state({"cells": [{"table": "holding"}]})   # a cells row without an address
    assert sc.cells[("holding", 0)].value == 7             # the bad file wiped nothing


def test_open_page_recovers_to_the_first_page_when_start_is_past_all_registers():
    # a scroll position past every served register must not strand the view above them (open_page
    # is what the import runs, but this holds for any too-high start)
    dev = FakeDevice({0: 1, 1: 2, 2: 3})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=4, max_read=4)
    sc.page(forward=True, anchor=0)
    state = sc.full_state()

    restored = scanner.Scanner(table="holding", start=0, count=4, max_read=4)   # offline (no reader)
    restored.load_state(state)
    restored.start = 50000                               # the session had scrolled way up
    restored.open_page()
    assert restored.start == 0                           # nothing is there, so drop to the first page
    rows = [r["address"] for r in restored.snapshot()["rows"]]
    assert rows and rows[0] == 0                          # landed on the served registers, not stranded


def test_generate_stamp_is_server_state_and_rides_in_exports():
    # the Manufacturer/Model stamp: seeded by a loaded device file, editable via set_meta,
    # part of the project export — and served in every snapshot, so a browser refresh
    # cannot lose it. The picked device FILE is deliberately not part of the export.
    doc = ("device: {manufacturer: Acme, model: X1}\n"
           "holding: {temp: {address: 0, ha: {platform: sensor, name: Temp}}}\n")
    sc = scanner.Scanner(FakeDevice({0: 7}).read, table="holding", start=0, count=4, max_read=4)
    sc.load_device(doc, "acme.yaml")
    assert sc.snapshot()["meta"] == {"manufacturer": "Acme", "model": "X1"}  # seeded from the file

    sc.set_meta("  ACME Corp ", "X1 rev B")                                  # edited in the UI
    assert sc.snapshot()["meta"] == {"manufacturer": "ACME Corp", "model": "X1 rev B"}

    state = sc.full_state()
    assert state["meta"] == {"manufacturer": "ACME Corp", "model": "X1 rev B"}
    # the export's whole surface — no key carries the picked bundled-file name
    # (additive overlays ride along with theirs: the name is the overlay's identity)
    assert set(state) == {"config", "connection", "scan_index", "meta", "mapping",
                          "additional", "override", "cells"}

    restored = scanner.Scanner(table="holding", start=0, count=4, max_read=4)
    restored.load_state(state)
    assert restored.meta == {"manufacturer": "ACME Corp", "model": "X1 rev B"}

    # an OLD export (no meta key) seeds the stamp from its mapping's device block
    del state["meta"]
    older = scanner.Scanner(table="holding", start=0, count=4, max_read=4)
    older.load_state(state)
    assert older.meta == {"manufacturer": "Acme", "model": "X1"}

    sc.clear_all()                                                           # the deliberate reset
    assert sc.meta == {"manufacturer": "", "model": ""}


def test_imported_mapping_is_remembered_and_switchable():
    # importing a project remembers its mapping for the session: the dropdown's
    # 'imported · …' entry can switch away (a bundled file, or none) and back —
    # with edits made while it was active included. Only Clear all forgets it.
    doc = ("device: {manufacturer: Acme, model: X1}\n"
           "holding: {temp: {address: 0, ha: {platform: sensor, name: Temp}}}\n")
    src = scanner.Scanner(FakeDevice({0: 7, 1: 8}).read, table="holding", start=0, count=4, max_read=4)
    src.load_device(doc, "acme.yaml")
    state = src.full_state()

    sc = scanner.Scanner(FakeDevice({0: 7, 1: 8}).read, table="holding", start=0, count=4, max_read=4)
    with pytest.raises(scanner.DeviceSchemaError):
        sc.load_imported()                                # nothing imported this session
    sc.load_state(state)
    assert sc.snapshot()["imported"] == {"manufacturer": "Acme", "model": "X1"}

    # edits while the imported mapping is active land in the remembered slot too
    sc.set_mapping("holding", 1, {"name": "Extra", "platform": "sensor"})
    sc.set_meta("Acme", "X1 rev B")

    sc.clear_device()                                     # the '— none —' switch: mapping off...
    assert sc.device is None
    assert sc.snapshot()["imported"] == {"manufacturer": "Acme", "model": "X1 rev B"}

    sc.load_imported()                                    # ...and back — edits included
    assert {e.ha.get("name") for e in sc.device.entities} == {"Temp", "Extra"}
    assert sc.meta == {"manufacturer": "Acme", "model": "X1 rev B"}
    assert sc.device_name == "imported.yaml"

    sc.clear_all()                                        # the deliberate reset forgets it
    assert sc.snapshot()["imported"] is None


def test_loading_a_device_file_seeds_its_known_dead_list():
    # a device file's bad_addresses hint marks those registers dead up front (skipped + hidden), so
    # resuming a project doesn't re-probe what the device is already known to refuse
    doc = ("device: {manufacturer: Acme, model: X1, bad_addresses: {holding: [5]}}\n"
           "holding: {temp: {address: 0, ha: {platform: sensor, name: Temp}}}\n")
    dev = FakeDevice({0: 7})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=8, max_read=8)
    sc.load_device(doc, "acme.yaml")
    assert ("holding", 5) in sc._bad                      # seeded from the file's known-dead list
    sc.scan()
    assert all(not (a <= 5 < a + n) for a, n in dev.reads)  # so it's skipped, not re-probed
    # ...but the plain view still lists it as a known-dead row (never probed, no cell behind it)
    assert _cell(sc.snapshot(), 5)["error"] == "not served"


def test_history_records_distinct_values_with_scan_and_time():
    dev = FakeDevice({0: 100, 1: 5})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=2, max_read=2)
    sc.scan()                       # first sighting -> one history entry
    dev.values[0] = 100
    sc.scan()                       # unchanged -> no new entry
    dev.values[0] = 110
    sc.scan()                       # changed -> a new entry
    hist = sc.history("holding", 0)["history"]
    assert [h["value"] for h in hist] == [100, 110]         # only distinct-from-previous values
    assert [h["scan"] for h in hist] == [1, 3]              # the scan index each was first seen
    assert all(isinstance(h["t"], float) for h in hist)     # with a wall-clock timestamp
    # a compact tail rides along in the row for the hover tooltip
    row = _cell(sc.snapshot(), 0)
    assert row["hist"] == [100, 110] and row["hist_len"] == 2


def test_history_is_capped_to_the_most_recent_entries():
    dev = FakeDevice({0: 0})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=1, max_read=1)
    for v in range(scanner.HISTORY_MAX + 20):
        dev.values[0] = v
        sc.scan()
    hist = [h["value"] for h in sc.history("holding", 0)["history"]]
    assert hist == list(range(20, scanner.HISTORY_MAX + 20))   # oldest dropped, newest kept
    assert len(_cell(sc.snapshot(), 0)["hist"]) == scanner.HISTORY_SPARK  # row tail is bounded


def test_history_names_the_mapped_entity_and_survives_import():
    dev = FakeDevice({0: 1, 1: 2})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=2, max_read=2)
    sc.scan()
    dev.values[0] = 9
    sc.scan()
    sc.set_mapping("holding", 0, {"name": "Counter", "platform": "sensor"})
    h = sc.history("holding", 0)
    assert h["entity"]["name"] == "Counter"                  # names the entity mapped there
    assert [e["value"] for e in h["history"]] == [1, 9]
    # an unread, unmapped register: empty history, no entity
    assert sc.history("holding", 500) == {"table": "holding", "address": 500, "history": [],
                                          "value": None, "changes": 0, "entity": None,
                                          "decode": None, "override": None}
    # the recorded history round-trips through export/import
    restored = scanner.Scanner(table="holding", start=0, count=2, max_read=2)
    restored.load_state(sc.full_state())
    assert [e["value"] for e in restored.history("holding", 0)["history"]] == [1, 9]


def test_history_decodes_through_a_single_word_mapping():
    # a register whose entity starts here and spans one word decodes its whole history
    # through the real codec; a multi-word entity cannot (history is per-register words)
    dev = FakeDevice({0: 250, 1: 7, 2: 3})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=3, max_read=4)
    sc.set_mapping("holding", 0, {"name": "Temp", "platform": "sensor", "scale": "0.1"})
    sc.set_mapping("holding", 1, {"name": "Wide", "platform": "sensor", "type": "uint32"})
    sc.scan()
    dev.values[0] = 253
    sc.scan()
    h = sc.history("holding", 0)
    assert h["decode"]["source"] == "entity" and h["decode"]["name"] == "Temp"
    assert h["decode"]["spec"]["multiplier"] == 0.1   # the UI builds its "uint16 x0.1" column label from this
    assert [e["decoded"] for e in h["history"]] == [25.0, 25.3]
    assert [e["value"] for e in h["history"]] == [250, 253]     # the raw words stay alongside
    hw = sc.history("holding", 1)
    assert hw["decode"] is None and all("decoded" not in e for e in hw["history"])


def test_history_decode_override_is_global_wins_and_clears():
    # the Details-view override is ONE global spec: every word-table register's history
    # decodes through it — mapped ones included — until it is unmapped
    dev = FakeDevice({0: 0x8005, 1: 7})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=2, max_read=2)
    sc.set_mapping("holding", 0, {"name": "Temp", "platform": "sensor", "scale": "0.1"})
    sc.scan()

    sc.set_override({"type": "int16"})
    h = sc.history("holding", 0)
    assert h["decode"] == {"source": "override"}                # wins over the mapped entity
    assert h["history"][-1]["decoded"] == 0x8005 - 0x10000      # int16 view, not the 0.1 scale
    assert h["override"] == {"type": "int16", "ha": {"platform": "sensor", "name": "override"}}
    # ...and it covers every other word-table register too, mapped or not
    assert sc.history("holding", 1)["decode"] == {"source": "override"}
    assert sc.history("input", 1)["decode"] == {"source": "override"}
    # bit tables read 0/1 and are left alone
    assert sc.history("coil", 1)["decode"] is None
    # the main table's decoded column stays the integration's truth, untouched — and the
    # snapshot carries the spec, so the UI can prefill its editor synchronously
    snap = sc.snapshot()
    assert _cell(snap, 0)["entity"]["decoded"] == round(0x8005 * 0.1, 10)
    assert snap["override"] == h["override"]

    sc.clear_override()
    h = sc.history("holding", 0)
    assert h["decode"]["source"] == "entity" and h["decode"]["name"] == "Temp"
    assert h["override"] is None
    assert sc.snapshot()["override"] is None

    # refused where it cannot work: a multi-word type — nothing changes
    with pytest.raises(scanner.DeviceSchemaError):
        sc.set_override({"type": "uint32"})
    assert sc.history("holding", 0)["override"] is None


def test_history_decode_override_maps_unmapped_registers_and_rides_in_exports():
    dev = FakeDevice({0: 1})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=1, max_read=1)
    sc.scan()
    sc.set_override({"map": "0: Off, 1: On"})                   # no mapping needed
    assert sc.history("holding", 0)["history"][-1]["decoded"] == "On"

    state = json.loads(json.dumps(sc.full_state()))             # a JSON round-trip, like the browser
    restored = scanner.Scanner(table="holding", start=0, count=1, max_read=1)
    restored.load_state(state)
    assert restored.override["map"] == {0: "Off", 1: "On"}      # int keys restored
    assert restored.history("holding", 0)["history"][-1]["decoded"] == "On"

    restored.clear_all()                                        # the deliberate reset forgets it
    assert restored.override is None
    # an old export without the key restores to none
    del state["override"]
    restored.load_state(state)
    assert restored.override is None


DEVICE_YAML = """
device: {manufacturer: Acme, model: Widget}
holding:
  temp: {address: 0, multiplier: 0.1, ha: {platform: sensor, name: Temperature}}
  mode: {address: 1, map: {0: "Off", 1: "On"}, ha: {platform: select, name: Mode}}
  power: {address: 3, type: uint32, ha: {platform: sensor, name: Power}}
  ghost: {address: 8, ha: {platform: sensor, name: Ghost}}
"""


def test_device_overlay_decodes_and_flags_conflicts():
    # 8 is refused; 2 is served but the file maps nothing there
    dev = FakeDevice({0: 250, 1: 1, 2: 42, 3: 0, 4: 1000}, illegal={8})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=10, max_read=8)
    summary = sc.load_device(DEVICE_YAML, "widget.yaml")
    assert summary["model"] == "Widget"
    assert summary["tables"]["holding"] == {"min": 0, "max": 8, "entities": 4}

    sc.scan()
    snap = sc.snapshot()
    assert snap["device"]["manufacturer"] == "Acme"

    # each mapped register decodes through the real codec (scale / map / uint32)
    assert _cell(snap, 0)["entity"]["name"] == "Temperature"
    assert _cell(snap, 0)["entity"]["decoded"] == 25.0            # 250 * 0.1
    assert _cell(snap, 1)["entity"]["decoded"] == "On"           # map 1 -> On
    p = _cell(snap, 3)["entity"]
    assert p["name"] == "Power" and p["count"] == 2 and p["decoded"] == 1000  # uint32 [0,1000]
    assert _cell(snap, 4)["entity"]["continuation"] is True      # second word of Power
    assert _cell(snap, 4)["entity"]["address"] == 3              # editing it edits Power

    # served but unmapped shows in the plain view (a gap the file misses)
    assert _cell(snap, 2)["entity"] is None and _cell(snap, 2)["value"] == 42
    # the file maps a dead address (8) — refused registers aren't in the plain view, but the mapped
    # view lists every mapped entity, so it surfaces there with its refusal flagged
    sc.reconfigure(table="holding", start=0, count=10, max_read=8, filter_mode="mapped", page_size=10)
    sc.page(forward=True, anchor=0)
    r8 = _cell(sc.snapshot(), 8)
    assert r8["error"] == "not served" and r8["entity"]["name"] == "Ghost"

    sc.clear_device()
    assert "entity" not in _cell(sc.snapshot(), 0) and sc.snapshot()["device"] is None


def test_interactive_mapping_add_edit_unmap_and_generate():
    dev = FakeDevice({0: 250, 1: 20}, illegal={5})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=6, max_read=4)
    sc.scan()

    # click an unmapped register -> map it as a scaled temperature sensor
    sc.set_mapping("holding", 0, {"name": "Temp", "platform": "sensor",
                                  "type": "uint16", "scale": "0.1", "unit": "°C"})
    e0 = _cell(sc.snapshot(), 0)["entity"]
    assert e0["name"] == "Temp" and e0["decoded"] == 25.0 and e0["address"] == 0
    assert _cell(sc.snapshot(), 1)["entity"] is None  # its neighbour is still unmapped

    # re-mapping the same address replaces it (here: drop the scale)
    sc.set_mapping("holding", 0, {"name": "Temp", "platform": "sensor", "type": "uint16"})
    assert _cell(sc.snapshot(), 0)["entity"]["decoded"] == 250

    # every mapped entity is in the generated file, even with nothing selected
    doc = yaml.safe_load(sc.generate_yaml("Acme", "Widget", []))
    device = parse_device(doc, "generated.yaml")
    assert [e.ha.get("name") for e in device.entities] == ["Temp"]

    # unmap: the last mapping gone clears the whole overlay
    sc.remove_mapping("holding", 0)
    assert sc.snapshot()["device"] is None


def test_mapping_rejects_invalid_entity_and_keeps_previous():
    dev = FakeDevice({0: 1, 1: 2})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=2, max_read=2)
    sc.scan()
    sc.set_mapping("holding", 0, {"name": "Good", "platform": "sensor"})

    # a select without a map is rejected by the real schema, and nothing changes
    with pytest.raises(scanner.DeviceSchemaError):
        sc.set_mapping("holding", 1, {"name": "Bad", "platform": "select"})
    names = [r["entity"]["name"] for r in sc.snapshot()["rows"] if r.get("entity")]
    assert names == ["Good"]


def test_filter_mapped_shows_every_register_of_multiword_entities():
    dev = FakeDevice({i: i + 1 for i in range(10)})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=10, max_read=8)
    sc.set_mapping("holding", 0, {"name": "Power", "platform": "sensor", "type": "uint32"})  # 2 registers
    sc.set_mapping("holding", 4, {"name": "Flow", "platform": "sensor"})                     # 1 register

    sc.reconfigure(table="holding", start=0, count=10, max_read=8, filter_mode="mapped", page_size=100)
    sc.page(forward=True, anchor=0)
    rows = sc.snapshot()["rows"]
    assert [r["address"] for r in rows] == [0, 1, 4]           # both words of Power, then Flow
    assert rows[0]["entity"]["name"] == "Power"
    assert rows[1]["entity"]["continuation"] is True           # the second word is shown too
    assert rows[1]["entity"]["address"] == 0                   # and still edits Power
    assert rows[2]["entity"]["name"] == "Flow"


def test_mapping_editor_number_formatting_fields():
    dev = FakeDevice({0: 100, 1: 5, 2: 50})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=4, max_read=4)
    sc.scan()

    # offset + precision + device_class on a scaled sensor: value = raw*scale + offset
    sc.set_mapping("holding", 0, {"name": "Temp", "platform": "sensor", "scale": "0.1",
                                  "offset": "-40", "precision": "1", "device_class": "temperature",
                                  "unit": "°C"})
    assert _cell(sc.snapshot(), 0)["entity"]["decoded"] == -30.0   # 100 * 0.1 - 40

    # a sum_scale counter spread over two registers
    sc.set_mapping("holding", 1, {"name": "Energy", "platform": "sensor", "sum_scale": "1, 10000"})
    assert _cell(sc.snapshot(), 2)["entity"]["continuation"] is True   # second element's register

    # all of it round-trips through the real schema
    device = parse_device(yaml.safe_load(sc.generate_yaml("Acme", "X", [])), "gen.yaml")
    temp = next(e for e in device.entities if e.ha.get("name") == "Temp")
    assert temp.multiplier == 0.1 and temp.offset == -40
    assert temp.ha.get("suggested_display_precision") == 1
    assert str(temp.ha.get("device_class")) == "temperature"
    energy = next(e for e in device.entities if e.ha.get("name") == "Energy")
    assert energy.sum_scale == (1.0, 10000.0) and energy.count == 2


def test_filter_mapped_packs_and_pages():
    dev = FakeDevice({i: i + 1 for i in range(20)})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=20, max_read=8)
    for addr, name in ((2, "A"), (10, "B"), (15, "C")):
        sc.set_mapping("holding", addr, {"name": name, "platform": "sensor"})

    # mapped filter, 2 per page -> the scattered mapped registers pack together and read live
    sc.reconfigure(table="holding", start=0, count=20, max_read=8, filter_mode="mapped", page_size=2)
    sc.page(forward=True, anchor=0)
    snap = sc.snapshot()
    assert snap["config"]["filter"] == ["mapped"]
    assert [r["address"] for r in snap["rows"]] == [2, 10]
    assert all(r["value"] is not None for r in snap["rows"])   # the page was read
    assert snap["at_start"] is True and snap["at_end"] is False

    sc.page(forward=True, anchor=snap["next_anchor"])          # -> last page: slides back to stay full
    snap2 = sc.snapshot()
    assert [r["address"] for r in snap2["rows"]] == [10, 15]    # only 15 is left, so 10 fills the page
    assert snap2["at_end"] is True and snap2["at_start"] is False

    sc.page(forward=False, anchor=snap2["prev_anchor"])        # -> back again
    assert [r["address"] for r in sc.snapshot()["rows"]] == [2, 10]


def test_switching_to_an_empty_filter_shows_no_matches_not_stale_rows():
    # a non-zero page has matches; switching to "mapped" with nothing mapped must not keep them
    dev = FakeDevice({0: 5, 1: 7, 2: 9})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=4, max_read=4)
    sc.reconfigure(table="holding", start=0, count=4, max_read=4, filter_mode="nonzero", page_size=10)
    sc.page(forward=True, anchor=0)
    assert [r["address"] for r in sc.snapshot()["rows"]]           # non-zero found matches

    sc.reconfigure(table="holding", start=0, count=4, max_read=4, filter_mode="mapped", page_size=10)
    sc.page(forward=True, anchor=0)
    snap = sc.snapshot()
    assert snap["rows"] == []                # nothing mapped -> genuinely empty, not the stale rows
    assert snap["at_start"] is True and snap["at_end"] is True


def test_filter_changed_shows_only_registers_that_moved():
    # 0..5 served (refused from 6 on, so the scan stops); only 1 and 4 move between reads
    dev = FakeDevice({0: 10, 1: 20, 2: 30, 3: 40, 4: 50, 5: 60}, illegal=set(range(6, 200)))
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=6, max_read=8)
    sc.reconfigure(table="holding", start=0, count=6, max_read=8, filter_mode="none", page_size=6)
    sc.page(forward=True, anchor=0)                 # first read — nothing has moved yet

    # nothing has changed yet -> the "changed" view is genuinely empty
    sc.reconfigure(table="holding", start=0, count=6, max_read=8, filter_mode="changed", page_size=6)
    sc.page(forward=True, anchor=0)
    assert sc.snapshot()["rows"] == []

    # move two registers and re-read them on the plain view so the change is recorded
    sc.reconfigure(table="holding", start=0, count=6, max_read=8, filter_mode="none", page_size=6)
    dev.values[1], dev.values[4] = 21, 51
    sc.page(forward=True, anchor=0)

    # the changed view now lists exactly the two that moved (and nothing static)
    sc.reconfigure(table="holding", start=0, count=6, max_read=8, filter_mode="changed", page_size=6)
    sc.page(forward=True, anchor=0)
    snap = sc.snapshot()
    assert snap["config"]["filter"] == ["changed"]
    assert [r["address"] for r in snap["rows"]] == [1, 4]
    assert all(r["changes"] >= 1 for r in snap["rows"])


def test_filter_mapped_changed_unions_mapped_and_moved_registers():
    # 0..5 served; 10 is refused. Map 2 (static), 3 (moves), and 10 (a wrong/refused address).
    # 3 and 4 move between reads; 0, 1, 5 stay static and unmapped.
    dev = FakeDevice({0: 10, 1: 20, 2: 30, 3: 40, 4: 50, 5: 60}, illegal={10})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=6, max_read=8)
    sc.reconfigure(table="holding", start=0, count=6, max_read=8, filter_mode="none", page_size=6)
    sc.page(forward=True, anchor=0)                            # baseline read of 0..5
    sc.set_mapping("holding", 2, {"name": "Static", "platform": "sensor"})
    sc.set_mapping("holding", 3, {"name": "Live", "platform": "sensor"})
    sc.set_mapping("holding", 10, {"name": "WrongAddr", "platform": "sensor"})  # device refuses it

    dev.values[3], dev.values[4] = 41, 51                     # 3 (mapped) and 4 (unmapped) move
    sc.page(forward=True, anchor=0)                           # re-read -> 3 and 4 gain a change

    sc.reconfigure(table="holding", start=0, count=6, max_read=8, filter_mode="mappedchanged", page_size=6)
    sc.page(forward=True, anchor=0)
    snap = sc.snapshot()
    assert snap["config"]["filter"] == ["changed", "mapped"]  # the legacy union name maps to the chips
    # union: 2, 3 (mapped) + 4 (moved) + 10 (mapped, even though refused — the set-based view never
    # drops a mapped register); 0, 1, 5 (static and unmapped) are excluded
    assert [r["address"] for r in snap["rows"]] == [2, 3, 4, 10]
    rows = {r["address"]: r for r in snap["rows"]}
    assert rows[2]["changes"] == 0 and rows[2]["error"] is None   # shown for being mapped, not for moving
    assert rows[4]["changes"] >= 1                                # shown for moving, though unmapped
    assert rows[10]["error"]                                      # a refused mapped address, still listed


def test_filter_xray_projects_sibling_mappings_onto_the_current_table():
    dev = FakeDevice({0: 10, 1: 20, 2: 30, 3: 40, 10: 7, 11: 3})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=12, max_read=16)
    sc.set_mapping("holding", 2, {"name": "Local", "platform": "sensor"})
    sc.set_mapping("input", 2, {"name": "Twin", "platform": "sensor"})    # sibling at a locally mapped addr
    sc.set_mapping("input", 0, {"name": "Volt", "platform": "sensor"})    # sibling only
    sc.set_mapping("input", 10, {"name": "Power", "platform": "sensor", "type": "uint32"})  # 2 registers
    sc.set_mapping("coil", 3, {"name": "Pump", "platform": "binary_sensor"})  # non-compatible table

    sc.reconfigure(table="holding", start=0, count=12, max_read=16, filter_mode="xray", page_size=10)
    sc.page(forward=True, anchor=0)
    snap = sc.snapshot()
    # membership: every address any table maps — holding {2}, input {0, 2, 10, 11}, coil {3}
    assert [r["address"] for r in snap["rows"]] == [0, 2, 3, 10, 11]
    rows = {r["address"]: r for r in snap["rows"]}
    # sibling-only: shown as if it were local (muted in the UI), decoded from HOLDING's registers
    assert rows[0]["entity"] is None
    assert rows[0]["xmap"]["table"] == "input" and rows[0]["xmap"]["name"] == "Volt"
    assert rows[0]["xmap"]["decoded"] == 10
    # locally mapped too: the local entity stays, the sibling arrives for the tiny corner tag
    assert rows[2]["entity"]["name"] == "Local" and rows[2]["xmap"]["name"] == "Twin"
    # non-compatible tables are named for the hover title, never shown as-if-local
    assert "xmap" not in rows[3] and rows[3]["xother"] == [{"table": "coil", "name": "Pump"}]
    # a multi-word sibling decodes from this table's words; its tail is a continuation
    assert rows[10]["xmap"]["decoded"] == (7 << 16) + 3
    assert rows[11]["xmap"]["continuation"] is True

    # outside the x-ray views the rows carry no x-ray payload (and mapped lists only local)
    sc.reconfigure(table="holding", start=0, count=12, max_read=16, filter_mode="mapped", page_size=10)
    sc.page(forward=True, anchor=0)
    snap = sc.snapshot()
    assert [r["address"] for r in snap["rows"]] == [2]
    assert all("xmap" not in r and "xother" not in r for r in snap["rows"])


def test_filter_xray_changed_adds_moved_registers():
    dev = FakeDevice({0: 1, 1: 2, 2: 3, 3: 4})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=4, max_read=8)
    sc.reconfigure(table="holding", start=0, count=4, max_read=8, filter_mode="none", page_size=4)
    sc.page(forward=True, anchor=0)                    # baseline read of 0..3
    sc.set_mapping("input", 0, {"name": "Volt", "platform": "sensor"})
    dev.values[3] = 5
    sc.page(forward=True, anchor=0)                    # re-read -> 3 gains a change

    sc.reconfigure(table="holding", start=0, count=4, max_read=8, filter_mode="xraychanged", page_size=4)
    sc.page(forward=True, anchor=0)
    snap = sc.snapshot()
    assert [r["address"] for r in snap["rows"]] == [0, 3]   # the projected mapping union the moved register
    rows = {r["address"]: r for r in snap["rows"]}
    assert rows[0]["xmap"]["name"] == "Volt"
    assert rows[3]["changes"] >= 1 and "xmap" not in rows[3]


def test_mapped_and_xray_views_list_write_only_registers_even_when_dead():
    # a write-only 3-register entity refuses every read; after two strikes its registers are
    # dead (_bad) — the mapped and x-ray views must still list all three rows (start + ↑ tails)
    dev = FakeDevice({0: 1}, illegal={4, 5, 6})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=8, max_read=8)
    sc.set_mapping("holding", 4, {"name": "Heat quantity pool", "platform": "sensor",
                                  "sum_scale": "1, 10000, 100000000"})
    for filt in ("mapped", "xray"):
        sc.reconfigure(table="holding", start=0, count=8, max_read=8, filter_mode=filt, page_size=8)
        sc.page(forward=True, anchor=0)
        sc.page(forward=True, anchor=0)                    # second refusal in a row -> dead
        assert {("holding", a) for a in (4, 5, 6)} <= sc._bad
        rows = sc.snapshot()["rows"]
        assert [r["address"] for r in rows] == [4, 5, 6], filt
        assert all(r["error"] for r in rows)
        assert rows[0]["entity"]["name"] == "Heat quantity pool"
        assert rows[1]["entity"]["continuation"] and rows[2]["entity"]["continuation"]


def test_xray_copy_adopts_the_sibling_mapping_locally():
    dev = FakeDevice({0: 10, 1: 20, 2: 30, 3: 40})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=4, max_read=8)
    sc.set_mapping("input", 2, {"name": "Volt", "platform": "sensor", "scale": "0.5"})
    sc.reconfigure(table="holding", start=0, count=4, max_read=8, filter_mode="xray", page_size=4)
    sc.page(forward=True, anchor=0)

    sc.copy_mapping("holding", 2)
    snap = sc.snapshot()
    row = {r["address"]: r for r in snap["rows"]}[2]
    assert row["entity"]["name"] == "Volt (holding)"   # local now, renamed to stay unique
    assert row["entity"]["decoded"] == 15.0            # 30 * 0.5 — the copied spec kept its scale
    assert row["xmap"]["name"] == "Volt"               # the sibling original is untouched
    # a generated device file carries both entities
    device = parse_device(yaml.safe_load(sc.generate_yaml("Acme", "X", [])), "gen.yaml")
    assert {(e.table, e.address) for e in device.entities} == {("holding", 2), ("input", 2)}
    # refused where it cannot work: already mapped here, or nothing starts on the sibling
    with pytest.raises(scanner.DeviceSchemaError):
        sc.copy_mapping("holding", 2)
    with pytest.raises(scanner.DeviceSchemaError):
        sc.copy_mapping("holding", 3)


ALT_DEVICE_YAML = """
device: {manufacturer: Other, model: Y2}
holding:
  temp_b: {address: 0, multiplier: 0.5, ha: {platform: sensor, name: Temp B}}
  flow_b: {address: 2, ha: {platform: sensor, name: Flow B}}
  wide_b: {address: 5, type: uint32, ha: {platform: sensor, name: Wide B}}
input:
  volt_b: {address: 2, ha: {platform: sensor, name: Volt B}}
"""


def test_additive_load_overlays_below_the_mapping():
    # the additive checkbox: a second device file stacks under the editable mapping as a
    # read-only comparison layer — the mapping, its stamp and its registers stay untouched
    dev = FakeDevice({0: 250, 1: 1, 2: 42, 3: 0, 4: 1000, 5: 2, 6: 3})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=8, max_read=8)
    sc.load_device(DEVICE_YAML, "widget.yaml")
    sc.load_device(ALT_DEVICE_YAML, "other.yaml", additive=True)
    sc.scan()
    snap = sc.snapshot()
    assert snap["device"]["name"] == "widget.yaml"                  # still THE mapping
    assert sc.meta == {"manufacturer": "Acme", "model": "Widget"}   # stamp untouched
    assert snap["additional"] == [{"name": "other.yaml", "manufacturer": "Other", "model": "Y2"}]

    # where the mapping already maps, the overlay hit rides along (the UI corners it)
    r0 = _cell(snap, 0)
    assert r0["entity"]["name"] == "Temperature" and r0["entity"]["decoded"] == 25.0
    a0 = r0["amaps"][0]
    assert (a0["src"], a0["table"], a0["name"]) == ("other.yaml", "holding", "Temp B")
    assert a0["decoded"] == 125.0                                   # 250 * 0.5, the real codec
    # where nothing maps, the overlay's entity fills (the UI greys it, tagged with the address)
    r2 = _cell(snap, 2)
    assert r2["entity"] is None
    assert r2["amaps"][0]["name"] == "Flow B" and r2["amaps"][0]["decoded"] == 42
    # multi-word overlay entities decode whole and carry ↑ continuations
    assert _cell(snap, 5)["amaps"][0]["decoded"] == (2 << 16) + 3
    assert _cell(snap, 6)["amaps"][0]["continuation"] is True
    # outside the x-ray views only the current table's overlay entities appear (input stays out)
    assert all(a["table"] == "holding" for r in snap["rows"] for a in r.get("amaps", []))


def test_additive_overlays_stack_in_load_order_and_join_the_set_views():
    dev = FakeDevice({0: 10, 1: 20, 30: 5})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=4, max_read=8)
    sc.load_device(DEVICE_YAML, "widget.yaml")                      # holding 0, 1, 3-4, 8
    sc.load_device(ALT_DEVICE_YAML, "other.yaml", additive=True)    # holding 0, 2, 5-6 + input 2
    third = ("device: {manufacturer: Third, model: Z3}\n"
             "holding: {alt_flow: {address: 2, ha: {platform: sensor, name: Flow C}}}\n"
             "input: {far: {address: 30, ha: {platform: sensor, name: Far C}}}\n")
    sc.load_device(third, "third.yaml", additive=True)

    # the mapped view's membership now includes every overlay's current-table registers
    sc.reconfigure(table="holding", start=0, count=4, max_read=8, filter_mode="mapped", page_size=20)
    sc.page(forward=True, anchor=0)
    snap = sc.snapshot()
    assert [r["address"] for r in snap["rows"]] == [0, 1, 2, 3, 4, 5, 6, 8]
    rows = {r["address"]: r for r in snap["rows"]}
    # two overlays map holding 2 — hits stay in load order (the UI fills with the first)
    assert [a["src"] for a in rows[2]["amaps"]] == ["other.yaml", "third.yaml"]
    assert all(a["table"] == "holding" for r in snap["rows"] for a in r.get("amaps", []))

    # the x-ray views treat each overlay like the mapping's own x-ray: sibling entities
    # project in (decoded against THIS table's registers) and join the membership
    sc.reconfigure(table="holding", start=0, count=4, max_read=8, filter_mode="xray", page_size=20)
    sc.page(forward=True, anchor=0)
    snap = sc.snapshot()
    rows = {r["address"]: r for r in snap["rows"]}
    assert 30 in rows                                               # third.yaml's input 30
    assert [(a["src"], a["table"]) for a in rows[2]["amaps"]] == [
        ("other.yaml", "holding"), ("other.yaml", "input"), ("third.yaml", "holding")]
    a30 = rows[30]["amaps"][0]
    assert (a30["src"], a30["table"], a30["name"]) == ("third.yaml", "input", "Far C")
    assert a30["decoded"] == 5                                      # holding 30's value


def test_plain_load_and_none_clear_the_additive_overlays():
    dev = FakeDevice({0: 1})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=2, max_read=2)
    sc.load_device(DEVICE_YAML, "widget.yaml")
    sc.load_device(ALT_DEVICE_YAML, "other.yaml", additive=True)
    assert [o.name for o in sc.additional] == ["other.yaml"]

    # re-loading an overlay's name refreshes it in place — no duplicate layer
    sc.load_device(ALT_DEVICE_YAML, "other.yaml", additive=True)
    assert [o.name for o in sc.additional] == ["other.yaml"]

    # a plain (non-additive) load replaces the mapping AND the overlays
    sc.load_device(DEVICE_YAML, "widget.yaml")
    assert sc.additional == []

    # — none — drops the mapping and every overlay, keeping the stats
    sc.load_device(ALT_DEVICE_YAML, "other.yaml", additive=True)
    sc.scan()
    sc.clear_devices()
    assert sc.device is None and sc.additional == []
    assert sc.cells                                                 # stats survive

    # with nothing loaded, an additive load is just a plain load (it becomes the mapping)
    sc.load_device(DEVICE_YAML, "widget.yaml", additive=True)
    assert sc.snapshot()["device"]["name"] == "widget.yaml" and sc.additional == []


def test_additive_overlay_stays_out_of_generate_dead_list_and_stamp():
    alt = ("device: {manufacturer: Other, model: Y2, bad_addresses: {holding: [7]}}\n"
           "holding: {flow_b: {address: 2, ha: {platform: sensor, name: Flow B}}}\n")
    dev = FakeDevice({0: 1, 2: 3})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=4, max_read=4)
    sc.load_device(DEVICE_YAML, "widget.yaml")
    sc.load_device(alt, "other.yaml", additive=True)
    assert ("holding", 7) not in sc._bad          # another model's dead list is not this device's
    assert sc.meta == {"manufacturer": "Acme", "model": "Widget"}
    device = parse_device(yaml.safe_load(sc.generate_yaml("Acme", "Widget", [])), "gen.yaml")
    assert {e.ha.get("name") for e in device.entities} == {"Temperature", "Mode", "Power", "Ghost"}


def test_adopt_copies_an_overlay_mapping_into_the_editable_mapping():
    dev = FakeDevice({0: 250, 2: 42})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=4, max_read=4)
    sc.load_device(DEVICE_YAML, "widget.yaml")
    sc.load_device(ALT_DEVICE_YAML, "other.yaml", additive=True)
    sc.scan()

    sc.adopt_mapping("holding", 2)
    row = _cell(sc.snapshot(), 2)
    assert row["entity"]["name"] == "Flow B"      # the name was free — kept as-is
    assert row["entity"]["decoded"] == 42
    # the adopted entity is the mapping's now: it rides into the generated file
    device = parse_device(yaml.safe_load(sc.generate_yaml("", "", [])), "gen.yaml")
    assert ("holding", 2) in {(e.table, e.address) for e in device.entities}
    # refused where it cannot work: already mapped here, or no overlay entity starts there
    with pytest.raises(scanner.DeviceSchemaError):
        sc.adopt_mapping("holding", 2)
    with pytest.raises(scanner.DeviceSchemaError):
        sc.adopt_mapping("holding", 1)
    # a taken display name gets a numbered suffix (the schema refuses duplicates)
    clash = ("device: {manufacturer: C, model: C}\n"
             "holding: {t2: {address: 9, ha: {platform: sensor, name: Temperature}}}\n")
    sc.load_device(clash, "clash.yaml", additive=True)
    sc.adopt_mapping("holding", 9)
    assert sc._starts[("holding", 9)].ha["name"] == "Temperature (2)"


def test_additive_overlays_ride_in_exports():
    sc = scanner.Scanner(FakeDevice({0: 1}).read, table="holding", start=0, count=2, max_read=2)
    sc.load_device(DEVICE_YAML, "widget.yaml")
    sc.load_device(ALT_DEVICE_YAML, "other.yaml", additive=True)
    state = json.loads(json.dumps(sc.full_state()))   # a JSON round-trip, like the browser does
    restored = scanner.Scanner(table="holding", start=0, count=2, max_read=2)
    restored.load_state(state)
    assert [o.name for o in restored.additional] == ["other.yaml"]
    assert restored.snapshot()["additional"][0]["manufacturer"] == "Other"
    # an old export without the key restores to no overlays
    del state["additional"]
    restored.load_state(state)
    assert restored.additional == []


def test_filter_chips_union_any_atom_combination():
    # the chip model: the filter is a SET of additive atoms — here "everything mapped plus
    # anything non-zero", a view the old single-value dropdown could not express
    dev = FakeDevice({1: 5, 3: 0, 8: 9})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=10, max_read=8)
    sc.set_mapping("holding", 3, {"name": "Mine reads zero", "platform": "sensor"})
    sc.reconfigure(table="holding", start=0, count=10, max_read=8,
                   filter_mode=["mapped", "nonzero", "bogus"], page_size=10)  # unknown atoms drop
    sc.page(forward=True, anchor=0)
    snap = sc.snapshot()
    assert [r["address"] for r in snap["rows"]] == [1, 3, 8]   # non-zero walk plus mapped member
    assert snap["config"]["filter"] == ["nonzero", "mapped"]   # canonical chip order, no 'bogus'


def test_filter_chip_refused_lists_only_dead_registers():
    # refused as its own atom: the rows the plain view greys, on their own page
    dev = FakeDevice({0: 1, 2: 3}, illegal={1, 4})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=5, max_read=8)
    sc.page(forward=True, anchor=0)
    sc.page(forward=True, anchor=0)                    # second refusal in a row -> dead
    sc.reconfigure(table="holding", start=0, count=5, max_read=8,
                   filter_mode=["refused"], page_size=5)
    sc.page(forward=True, anchor=0)
    rows = sc.snapshot()["rows"]
    assert [r["address"] for r in rows] == [1, 4]
    assert all(r["error"] for r in rows)


def test_filter_members_keep_far_known_matches_beyond_the_walk_stop():
    # a changed register far past a long refused run: the walk stops at the dead run, but the
    # atom's already-known members still bring it in — a match you have seen is never lost
    dev = FakeDevice({0: 10, 500: 7}, illegal=set(range(2, 400)))
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=2, max_read=64)
    sc.page(forward=True, anchor=0)                    # baseline read around 0
    sc.reconfigure(table="holding", start=500, count=2, max_read=64)
    sc.page(forward=True, anchor=500)                  # baseline read around 500
    dev.values[0], dev.values[500] = 11, 8
    sc.page(forward=True, anchor=500)                  # 500 moves...
    sc.reconfigure(table="holding", start=0, count=2, max_read=64)
    sc.page(forward=True, anchor=0)                    # ...and 0 moves
    sc.reconfigure(table="holding", start=0, count=4, max_read=64,
                   filter_mode=["changed"], page_size=4)
    sc.page(forward=True, anchor=0)
    assert [r["address"] for r in sc.snapshot()["rows"]] == [0, 500]


def test_search_by_value_matches_raw_int16_and_hex():
    # '=value' terms search the LAST-KNOWN values: the raw word, its int16 view, hex input —
    # and terms still OR with the others (here an address term)
    dev = FakeDevice({0: 65449, 1: 87, 2: 42})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=3, max_read=4)
    sc.scan()
    for term, want in (("=-87", [0]), ("=65449", [0]), ("=0xFFA9", [0]),
                       ("=87", [1]), ("=87, 2", [1, 2])):
        sc.reconfigure(table="holding", start=0, count=3, max_read=4, page_size=3, search=term)
        sc.page(forward=True, anchor=0)
        assert [r["address"] for r in sc.snapshot()["rows"]] == want, term


def test_search_by_value_matches_float_pairs_at_typed_precision():
    # a decimal term checks the float readings of adjacent registers, BOTH word orders,
    # and matches at the precision typed: =42.5 covers 42.45..42.55, =42.50 does not.
    # (The device serves only 10..21 — a zero next to a float's high word would itself
    # read as a round float in one word order, which is honest but not this test's point.)
    hi, lo = struct.unpack(">HH", struct.pack(">f", 42.53))
    dev = FakeDevice({10: hi, 11: lo, 20: lo, 21: hi},
                     illegal=set(range(0, 10)) | set(range(22, 60)))
    sc = scanner.Scanner(dev.read, table="holding", start=10, count=12, max_read=16)
    sc.scan()
    sc.reconfigure(table="holding", start=10, count=12, max_read=16, page_size=12, search="=42.5")
    sc.page(forward=True, anchor=0)
    assert [r["address"] for r in sc.snapshot()["rows"]] == [10, 20]
    sc.reconfigure(table="holding", start=10, count=12, max_read=16, page_size=12, search="=42.50")
    sc.page(forward=True, anchor=0)
    assert sc.snapshot()["rows"] == []                   # two decimals ask for more than 42.53 gives


def test_search_by_value_matches_uint32_pairs_and_decoded_entities():
    dev = FakeDevice({0: 1, 1: 34464, 5: 235})           # (1, 34464) reads 100000 as uint32
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=6, max_read=8)
    sc.set_mapping("holding", 5, {"name": "Temp", "platform": "sensor", "scale": "0.1"})
    sc.scan()
    sc.reconfigure(table="holding", start=0, count=6, max_read=8, page_size=6, search="=100000")
    sc.page(forward=True, anchor=0)
    assert [r["address"] for r in sc.snapshot()["rows"]] == [0]
    sc.reconfigure(table="holding", start=0, count=6, max_read=8, page_size=6, search="=23.5")
    sc.page(forward=True, anchor=0)
    assert [r["address"] for r in sc.snapshot()["rows"]] == [5]   # Temp's decoded 23.5, no raw word


def test_search_finds_overlay_names_on_the_current_table():
    dev = FakeDevice({2: 42})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=4, max_read=4)
    sc.load_device(DEVICE_YAML, "widget.yaml")
    sc.load_device(ALT_DEVICE_YAML, "other.yaml", additive=True)
    sc.reconfigure(table="holding", start=0, count=4, max_read=4, filter_mode="none",
                   page_size=4, search="flow b")
    sc.page(forward=True, anchor=0)
    assert [r["address"] for r in sc.snapshot()["rows"]] == [2]


def test_filter_nonzero_scans_to_fill_and_pages():
    # non-zero at 1, 3, 8; the rest read zero; refused from 20 on (the register map ends there)
    dev = FakeDevice({1: 5, 3: 7, 8: 9}, illegal=set(range(20, 200)))
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=8, max_read=4)
    sc.reconfigure(table="holding", start=0, count=8, max_read=4, filter_mode="nonzero", page_size=2)

    sc.page(forward=True, anchor=0)
    snap = sc.snapshot()
    assert [r["address"] for r in snap["rows"]] == [1, 3]      # scanned forward, skipping zeros
    assert all(r["value"] for r in snap["rows"])
    assert snap["at_start"] is True and snap["at_end"] is False

    # paging forward reads past the zeros to 8; it's the last match, so the page slides back to fill
    sc.page(forward=True, anchor=snap["next_anchor"])
    snap2 = sc.snapshot()
    assert [r["address"] for r in snap2["rows"]] == [3, 8]     # only 8 is left, so 3 fills the page
    assert snap2["at_end"] is True

    sc.page(forward=False, anchor=snap2["prev_anchor"])        # back to the first matches
    assert [r["address"] for r in sc.snapshot()["rows"]] == [1, 3]

    # turning the filter off shows the served registers (packed), reading past the refused tail
    sc.reconfigure(table="holding", start=0, count=8, max_read=4, filter_mode="none", page_size=8)
    sc.page(forward=True, anchor=0)
    assert [r["address"] for r in sc.snapshot()["rows"]] == list(range(8))


def test_paging_to_the_start_slides_the_window_to_fill_the_page():
    # Start high with few registers below (0 refused): paging left must fill the page by sliding up,
    # not leave a half-empty stub of the few registers that happen to sit below the anchor
    dev = FakeDevice({i: i for i in range(1, 40)}, illegal={0})  # 0 refused; 1..39 served
    sc = scanner.Scanner(dev.read, table="holding", start=6, count=8, max_read=8)
    sc.reconfigure(table="holding", start=6, count=8, max_read=8, filter_mode="served", page_size=8)

    sc.page(forward=True, anchor=6)
    snap = sc.snapshot()
    assert [r["address"] for r in snap["rows"]] == [6, 7, 8, 9, 10, 11, 12, 13]   # a full page from 6

    sc.page(forward=False, anchor=snap["prev_anchor"])          # page left — only 1..5 sit below 6
    left = sc.snapshot()
    assert [r["address"] for r in left["rows"]] == [1, 2, 3, 4, 5, 6, 7, 8]       # slid up to stay full
    assert left["at_start"] is True                             # nothing below register 1


def test_filter_nonzero_does_not_page_past_the_last_match():
    # a full page followed by nothing must land on at_end — not offer a dead page into empty space
    dev = FakeDevice({0: 1, 1: 2, 5: 3, 6: 4}, illegal=set(range(7, 200)))
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=8, max_read=4)
    sc.reconfigure(table="holding", start=0, count=8, max_read=4, filter_mode="nonzero", page_size=2)

    sc.page(forward=True, anchor=0)
    snap = sc.snapshot()
    assert [r["address"] for r in snap["rows"]] == [0, 1]
    assert snap["next_anchor"] == 5     # the real next match (look-ahead), not 2 = one-past-the-page

    sc.page(forward=True, anchor=snap["next_anchor"])
    snap2 = sc.snapshot()
    assert [r["address"] for r in snap2["rows"]] == [5, 6]
    assert snap2["at_end"] is True and snap2["next_anchor"] is None  # a full page, but nothing beyond


def test_mapping_editor_covers_the_integration_fields():
    dev = FakeDevice({0: 0x12FF, 1: 5, 2: 3, 3: 0, 4: 0})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=6, max_read=6)
    sc.scan()

    # masked int16 sensor with swap + icon + diagnostic category + a free-form advanced block
    sc.set_mapping("holding", 0, {"name": "Status", "platform": "sensor", "type": "int16",
                                  "swap": "byte", "mask": "0xFF", "icon": "mdi:flash",
                                  "entity_category": "diagnostic",
                                  "advanced": "never_resets: true\nha: {enabled_by_default: false}"})
    sc.set_mapping("holding", 1, {"name": "Alarms", "platform": "sensor", "flags": "0: fault, 1: warn"})
    sc.set_mapping("holding", 2, {"name": "Counter", "platform": "number", "sum_scale": "1, 10000",
                                  "min": "0", "max": "100000000"})   # sum_scale now works on number
    sc.set_mapping("holding", 4, {"name": "Reset", "platform": "button", "write_value": "1"})
    sc.set_mapping("holding", 3, {"name": "Power sw", "platform": "switch",
                                  "on_value": "0x10", "off_value": "0"})   # hex accepted, like mask

    device = parse_device(yaml.safe_load(sc.generate_yaml("Acme", "X", [])), "gen.yaml")
    by_name = {e.ha.get("name"): e for e in device.entities}
    status = by_name["Status"]
    assert status.mask == 0xFF and status.swap == "byte"
    assert by_name["Power sw"].on_value == 0x10 and by_name["Power sw"].off_value == 0
    assert status.ha.get("icon") == "mdi:flash" and str(status.ha.get("entity_category")) == "diagnostic"
    assert status.never_resets is True                                 # from the advanced block
    assert status.ha.get("entity_registry_enabled_default") is False   # advanced ha alias resolved
    assert by_name["Alarms"].flags == {0: "fault", 1: "warn"}
    assert by_name["Counter"].sum_scale == (1.0, 10000.0) and by_name["Counter"].platform == "number"
    assert by_name["Reset"].write_value == 1 and by_name["Reset"].platform == "button"


def test_generate_puts_translations_last():
    doc = ("device: {manufacturer: Acme, model: M}\n"
           "holding:\n  temp: {address: 0, ha: {platform: sensor, name: Temperature}}\n"
           "translations:\n  Temperature: {en: Temperature, de: Temperatur}\n")
    sc = scanner.Scanner(FakeDevice({0: 1}).read, table="holding", start=0, count=1, max_read=1)
    sc.load_device(doc, "m.yaml")
    text = sc.generate_yaml("Acme", "M", [])
    assert text.index("holding:") < text.index("translations:")   # tables before the catalog
    parse_device(yaml.safe_load(text), "gen.yaml")                 # still valid


def test_range_is_clamped_to_the_address_space():
    sc = scanner.Scanner(table="holding", start=0, count=64, max_read=8)
    sc.reconfigure(table="holding", start=0, count=999999, max_read=8)
    assert sc.start == 0 and sc.count == 65536             # all registers, capped at the top
    sc.reconfigure(table="holding", start=70000, count=100, max_read=8)
    assert sc.start == 0xFFFF and sc.count == 1            # start past the end -> just the last one
    sc.reconfigure(table="holding", start=65500, count=1000, max_read=8)
    assert sc.start == 65500 and sc.count == 36            # count capped so it stays in range
    sc.reconfigure(table="holding", start=0, count=0, max_read=8)
    assert sc.count == 1                                   # count floored to 1
    # the constructor clamps too (a wild CLI --count)
    assert scanner.Scanner(table="holding", start=5, count=10**9, max_read=8).count == 65531

    # per-read is clamped to the protocol per-request limit, which differs by table
    sc.reconfigure(table="holding", start=0, count=64, max_read=5000)
    assert sc.max_read == 125                              # 125 registers max
    sc.reconfigure(table="coil", start=0, count=64, max_read=5000)
    assert sc.max_read == 2000                             # 2000 bits max
    sc.reconfigure(table="holding", start=0, count=64, max_read=0)
    assert sc.max_read == 1                                # floored to 1


def test_paging_stays_retryable_when_reads_go_silent_and_advances_on_recovery():
    # the reported bug: a slow/silent endpoint must not be mistaken for "no more registers".
    # An unreadable stretch keeps the page AND the ▶ / ◀ anchors (so paging retries), names
    # the failure, and advances the moment the device answers.
    dev = FakeDevice({i: i + 1 for i in range(20)})
    silent_at = [None]   # reads whose block reaches >= this address answer nothing

    def read(table, address, count):
        if silent_at[0] is not None and address + count > silent_at[0]:
            return scanner.ReadResult(None, "no answer from device ID 20", no_device=True)
        return dev.read(table, address, count)

    sc = scanner.Scanner(read, table="holding", start=0, count=4, max_read=4)
    sc.page(forward=True, anchor=0)
    snap = sc.snapshot()
    assert [r["address"] for r in snap["rows"]] == [0, 1, 2, 3]
    assert snap["at_end"] is False and snap["next_anchor"] == 4 and snap["last_error"] is None

    silent_at[0] = 4                          # the device goes quiet just past the page
    sc.page(forward=True, anchor=4)           # ▶ — nothing readable there right now
    snap = sc.snapshot()
    assert [r["address"] for r in snap["rows"]] == [0, 1, 2, 3]   # page kept, not blanked
    assert snap["at_end"] is False and snap["next_anchor"] == 4   # ▶ stays enabled to retry
    assert "no answer" in snap["last_error"]                      # and the failure is named

    silent_at[0] = None                       # the device recovers
    sc.page(forward=True, anchor=4)           # the retried ▶ now advances
    snap = sc.snapshot()
    assert [r["address"] for r in snap["rows"]] == [4, 5, 6, 7]
    assert snap["last_error"] is None

    # look-ahead-only silence: the page itself filled, only the probe past it timed out —
    # the anchor is synthesized so ▶ stays enabled (the edge beyond is unknown, not the end)
    silent_at[0] = 4
    sc2 = scanner.Scanner(read, table="holding", start=0, count=4, max_read=4)
    sc2.page(forward=True, anchor=0)
    snap = sc2.snapshot()
    assert [r["address"] for r in snap["rows"]] == [0, 1, 2, 3]
    assert snap["at_end"] is False and snap["next_anchor"] == 4


def test_paging_retries_a_slow_first_read_and_advances():
    # the reported ▶ bug: the first touch of a fresh region often times out on a slow gateway
    # (or a stale reply desyncs it), which used to abort the walk with "no answer". A bounded
    # retry drains it and lets paging advance — the device IS answering, just slowly.
    dev = FakeDevice({i: i + 1 for i in range(20)})
    attempts: dict = {}

    def read(table, address, count):
        k = (address, count)
        attempts[k] = attempts.get(k, 0) + 1
        if attempts[k] == 1:            # the FIRST attempt at any block times out; the retry works
            return scanner.ReadResult(None, "no answer from device ID 20", no_device=True)
        return dev.read(table, address, count)

    sc = scanner.Scanner(read, table="holding", start=0, count=4, max_read=4)
    sc.page(forward=True, anchor=0)
    snap = sc.snapshot()
    assert [r["address"] for r in snap["rows"]] == [0, 1, 2, 3]   # the retry recovered the read
    assert snap["last_error"] is None and snap["at_end"] is False
    sc.page(forward=True, anchor=snap["next_anchor"])             # ▶ now advances, not "no answer"
    assert [r["address"] for r in sc.snapshot()["rows"]] == [4, 5, 6, 7]


def test_single_probes_are_counted_per_operation_and_reported():
    # a refused block is downgraded to register-by-register probes (_bisect) — the snapshot
    # reports how many, per operation, so the UI can explain a suddenly slow scan
    dev = FakeDevice({0: 1, 1: 2, 3: 4}, illegal={2})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=4, max_read=4)
    sc.scan()
    assert sc.snapshot()["single_probes"] == 4     # the whole refused block was bisected
    sc.scan()
    assert sc.snapshot()["single_probes"] == 4     # 2 needs a second strike -> bisected again
    sc.scan()                                      # 2 is dead now: planned around, no bisect
    assert sc.snapshot()["single_probes"] == 0


def test_a_silent_register_region_is_bisected_and_isolated_when_the_link_is_alive():
    # the reported gateway: registers 5..8 are unsupported and the device serves them by NOT
    # answering (a timeout), not a refusal — so a block spanning them times out whole. With the
    # device answering its neighbours (0..4), the block is bisected: the good ones show, and the
    # silent ones are struck toward the dead list so later reads skip them (no endless "no answer").
    dead = {5, 6, 7, 8}
    vals = {i: i + 1 for i in range(20) if i not in dead}

    def read(table, address, count):
        for a in range(address, address + count):
            if a in dead:
                return scanner.ReadResult(None, "no answer from device ID 20", no_device=True)
        return scanner.ReadResult([vals.get(a, 0) for a in range(address, address + count)])

    sc = scanner.Scanner(read, table="holding", start=0, count=12, max_read=4)
    sc.scan()                                     # [0..3] answers (link proven alive), then the
    snap = sc.snapshot()                          # blocks spanning 5..8 are bisected and isolated
    assert _cell(snap, 4)["value"] == 5           # the good registers before the hole show
    assert _cell(snap, 5)["error"] == "not served"   # the silent ones are marked, not a blanket error
    assert snap["single_probes"] > 0              # the bisection is reported to the header
    assert snap["last_error"] is None             # NOT "no answer" — the link is alive, holes isolated

    sc.scan()                                     # a second strike seals them onto the dead list
    assert {("holding", a) for a in dead} <= sc._bad
    dev_reads = []
    sc._read = lambda t, a, n: (dev_reads.append((a, n)), read(t, a, n))[1]
    sc.scan()                                     # now planned around: no read spans the dead hole
    assert all(not (a <= 5 < a + n) for a, n in dev_reads)


def test_a_briefly_silent_link_is_not_buried_and_recovers():
    # the opposite: when the WHOLE link goes quiet for a scan (nothing answers), no register is
    # marked dead on the strength of that silence — it stays retryable and recovers cleanly.
    dev = FakeDevice({i: i + 1 for i in range(8)})
    down = [False]

    def read(table, address, count):
        return (scanner.ReadResult(None, "no answer from device ID 20", no_device=True)
                if down[0] else dev.read(table, address, count))

    sc = scanner.Scanner(read, table="holding", start=0, count=8, max_read=4)
    sc.scan()                                     # 0..7 answer -> the device is known alive
    down[0] = True                                # the whole link goes quiet
    sc.scan()
    assert "no answer" in sc.snapshot()["last_error"]
    assert not sc._bad                            # NOTHING buried on silence alone
    down[0] = False                               # it comes back
    sc.scan()
    assert [r["address"] for r in sc.snapshot()["rows"]] == list(range(8))
    assert sc.snapshot()["last_error"] is None


def test_a_small_count_reads_only_that_many_registers():
    # "read only 3 if it has to read only 3": the plain view must not blast a full max_read
    # block when Count is small — the read is sized to Count, plus a 1-register look-ahead
    dev = FakeDevice({i: i + 1 for i in range(200)})
    probed = []
    sc = scanner.Scanner(dev.read, table="holding", start=64, count=3, max_read=64)
    orig = sc._read
    sc._read = lambda t, a, n: (probed.append((a, n)), orig(t, a, n))[1]
    sc.scan()
    assert [r["address"] for r in sc.snapshot()["rows"]] == [64, 65, 66]
    assert max(a + n - 1 for a, n in probed) <= 67   # 64..66 (Count) + a 1-register peek at 67


def test_scanning_a_dead_edge_does_not_probe_far_beyond_the_range():
    # the reported bug: a Count=8 scan of 116..123 (with 120+ dead by timeout) must isolate
    # 120..123 but NOT go bisecting a full block deep past 123 via the look-ahead
    dead = set(range(120, 400))

    def read(table, address, count):
        for a in range(address, address + count):
            if a in dead:
                return scanner.ReadResult(None, "no answer from device ID 20", no_device=True)
        return scanner.ReadResult([a + 1 for a in range(address, address + count)])

    probed = []
    sc = scanner.Scanner(read, table="holding", start=116, count=8, max_read=64)
    sc._device_seen = True                         # the connect probe would set this in real use
    orig = sc._read
    sc._read = lambda t, a, n: (probed.append((a, n)), orig(t, a, n))[1]
    sc.scan()
    snap = sc.snapshot()
    assert [r["address"] for r in snap["rows"]] == list(range(116, 124))   # 116..123 shown
    assert _cell(snap, 123)["error"] == "not served"                       # dead edge isolated
    assert max(a + n - 1 for a, n in probed) <= 124   # never deep past the page (only a peek at 124)
    assert snap["single_probes"] == 8                 # just the in-range block, not 64+ beyond


def test_connect_probe_warning_self_heals_on_the_next_answering_scan(monkeypatch):
    # the probe warned (device silent at connect), but the device is really just slow: the
    # first answering read — data OR a refusal — must clear the warning, all on its own
    answers = [False]

    def waking(host, port, device_id, timeout, retries):
        def read(table, address, count):
            if not answers[0]:
                return scanner.ReadResult(None, f"no answer from device ID {device_id}",
                                          no_device=True)
            return scanner.ReadResult([7] * count)
        return read, (lambda: True), (lambda: None)

    monkeypatch.setattr(scanner, "pymodbus_reader", waking)
    sc = scanner.Scanner(table="holding", start=0, count=4, max_read=4)
    sc.connect(mode="tcp", host="gw.example", port=502, device_id=20)
    assert "device ID 20" in sc.conn_error          # probe (and its retry) found silence
    assert sc.snapshot()["connection"]["error"] == sc.conn_error

    answers[0] = True                               # the device wakes up
    sc.scan()
    assert sc.conn_error is None                    # the answering scan disproves the warning
    assert sc.snapshot()["connection"]["error"] is None


def _fake_gateway(result):
    """A pymodbus_reader stand-in whose every read answers ``result`` (TCP always connects)."""
    def reader(host, port, device_id, timeout, retries):
        def read(table, address, count):
            return result
        return read, (lambda: True), (lambda: None)
    return reader


def test_connect_probe_warns_when_the_device_id_never_answers(monkeypatch):
    # the classic gateway trap: TCP connects for ANY device ID, and only a read reveals
    # whether something answers behind it. The probe warns — and stays connected (a hint,
    # not a refusal: the ID may be wrong, or the device may just be offline).
    monkeypatch.setattr(scanner, "pymodbus_reader", _fake_gateway(
        scanner.ReadResult(None, "no answer from device ID 1", no_device=True)))
    sc = scanner.Scanner(table="holding", start=0, count=4, max_read=4)
    sc.connect(mode="tcp", host="gw.example", port=502, device_id=1)
    assert sc.connected
    assert "device ID 1" in sc.conn_error and "Device ID" in sc.conn_error
    assert sc.snapshot()["connection"]["error"] == sc.conn_error   # the UI banner sees it

    # ANY answer proves a device is there — even a refusal of the probed address...
    monkeypatch.setattr(scanner, "pymodbus_reader", _fake_gateway(
        scanner.ReadResult(None, "exception 2", illegal=True)))
    sc.connect(mode="tcp", host="gw.example", port=502, device_id=20)
    assert sc.connected and sc.conn_error is None

    # ...or a plain data answer, or a non-gateway exception (the device spoke)
    monkeypatch.setattr(scanner, "pymodbus_reader", _fake_gateway(
        scanner.ReadResult([7])))
    sc.connect(mode="tcp", host="gw.example", port=502, device_id=20)
    assert sc.connected and sc.conn_error is None
    monkeypatch.setattr(scanner, "pymodbus_reader", _fake_gateway(
        scanner.ReadResult(None, "exception 4")))
    sc.connect(mode="tcp", host="gw.example", port=502, device_id=20)
    assert sc.connected and sc.conn_error is None


def test_connect_demo_and_disconnected_guard():
    sc = scanner.Scanner(table="holding", start=0, count=4, max_read=4)  # no reader
    assert not sc.connected
    sc.scan()  # a no-op until connected
    snap = sc.snapshot()
    assert snap["connection"]["connected"] is False
    assert snap["scan_index"] == 0 and snap["last_error"] == "not connected"

    sc.connect(mode="demo")  # the UI's "Connect" with mode=Demo
    assert sc.connected
    assert sc.snapshot()["connection"]["mode"] == "demo"
    sc.scan()
    assert sc.snapshot()["scan_index"] == 1  # scanning works once connected


def test_reconnect_keeps_state_and_only_clear_all_wipes_it():
    # accumulate the lot: a mapping, per-register stats/history, a scan on the clock, and a
    # given-up-on (dead) register — the state a user would hate to lose by just reconnecting
    doc = ("device: {manufacturer: Acme, model: X1}\n"
           "holding: {temp: {address: 0, ha: {platform: sensor, name: Temp}}}\n")
    dev = FakeDevice({0: 7, 1: 8}, illegal={2})
    sc = scanner.Scanner(dev.read, table="holding", start=0, count=4, max_read=4)
    sc.load_device(doc, "acme.yaml")
    sc.scan()
    sc._read_range(2, 1)   # two refusals in a row ->
    sc._read_range(2, 1)   # address 2 is given up on
    assert sc.cells and sc.scan_index == 1
    assert ("holding", 2) in sc._bad and sc.map_doc is not None

    # Reconnecting must NOT throw any of that away — importing a project then connecting to watch it
    # live is exactly why a reconnect now keeps the stats, mapping and dead-list intact
    sc.connect(mode="demo")
    assert sc.connected
    assert sc.cells and sc.scan_index == 1
    assert ("holding", 2) in sc._bad and sc.map_doc is not None

    # Clear all is the one deliberate reset: mapping, stats, history and dead-list all go, and the
    # dead addresses are re-armed so the next scan probes them again
    sc.clear_all()
    assert not sc.cells and not sc._bad and sc._misses == {}
    assert sc.scan_index == 0 and sc.map_doc is None and sc.device is None


def test_disconnect_drops_the_link_but_keeps_everything():
    # the Connect button's other half: a deliberate drop, not a failure — so no error is
    # shown, the settings stay for the next Connect, and nothing gathered is lost
    doc = ("device: {manufacturer: Acme, model: X1}\n"
           "holding: {temp: {address: 0, ha: {platform: sensor, name: Temp}}}\n")
    sc = scanner.Scanner(table="holding", start=0, count=4, max_read=4)
    sc.connect(mode="demo")
    sc.load_device(doc, "acme.yaml")
    sc.scan()
    assert sc.connected and sc.cells and sc.scan_index == 1

    sc.disconnect()
    snap = sc.snapshot()
    assert not sc.connected and snap["connection"]["connected"] is False
    assert snap["connection"]["error"] is None
    assert snap["connection"]["mode"] == "demo"
    assert sc.cells and sc.scan_index == 1 and sc.map_doc is not None
    sc.scan()  # back to the disconnected guard
    assert sc.snapshot()["last_error"] == "not connected"

    sc.connect(mode="demo")  # and Connect brings the link straight back
    assert sc.connected and sc.cells and sc.snapshot()["last_error"] is None


def test_lists_bundled_device_files():
    devices = {d["file"] for d in scanner.list_device_files()}
    assert "solax-x3-hac.yaml" in devices
    assert "test.yaml" not in devices  # the example is excluded


def test_decoded_views_reads_a_float32():
    import struct

    hi, lo = struct.unpack(">HH", struct.pack(">f", 42.5))
    views = {v["type"]: v["value"] for v in scanner.decoded_views([hi, lo])}
    assert views["float32"] == repr(42.5)
    assert "uint32" in views and "string" in views
