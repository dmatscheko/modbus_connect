"""The standalone register scanner (support/modbus_scanner): scan bookkeeping,
learned-bad-address skipping (via the integration's planner), cross-table value
memory, the interactive mapping (add/edit/unmap, validated by the real schema),
and — most important — that the device-file it generates is valid against the schema."""

import importlib.util
import json
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
    assert restored.table == "holding" and restored.filter == "none"  # the view is left untouched

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
    assert set(state) == {"config", "connection", "scan_index", "meta", "mapping", "cells"}

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
                                          "value": None, "changes": 0, "entity": None}
    # the recorded history round-trips through export/import
    restored = scanner.Scanner(table="holding", start=0, count=2, max_read=2)
    restored.load_state(sc.full_state())
    assert [e["value"] for e in restored.history("holding", 0)["history"]] == [1, 9]


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
    assert snap["config"]["filter"] == "mapped"
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
    assert snap["config"]["filter"] == "changed"
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
    assert snap["config"]["filter"] == "mappedchanged"
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
