"""Tests for the read-block planner."""

from custom_components.modbus_connect.models import Span
from custom_components.modbus_connect.planner import (
    bridged_addresses,
    plan_blocks,
    spans_in_block,
)


def s(start: int, count: int = 1, table: str = "holding") -> Span:
    return Span(table, start, count)


def test_adjacent_spans_merge():
    blocks = plan_blocks([s(0, 2), s(2, 2)], max_read=100)
    assert blocks == [s(0, 4)]


def test_overlapping_and_duplicate_spans_merge():
    blocks = plan_blocks([s(0, 4), s(2, 4), s(0, 4)], max_read=100)
    assert blocks == [s(0, 6)]


def test_gap_bridged_within_max_gap():
    blocks = plan_blocks([s(0, 2), s(6, 2)], max_read=100, max_gap=4)
    assert blocks == [s(0, 8)]


def test_gap_not_bridged_beyond_max_gap():
    blocks = plan_blocks([s(0, 2), s(7, 2)], max_read=100, max_gap=4)
    assert blocks == [s(0, 2), s(7, 2)]


def test_zero_gap_only_merges_adjacent():
    blocks = plan_blocks([s(0, 2), s(2, 1), s(4, 1)], max_read=100, max_gap=0)
    assert blocks == [s(0, 3), s(4, 1)]


def test_holes_prevent_bridging():
    holes = {("holding", 3)}
    blocks = plan_blocks([s(0, 2), s(6, 2)], max_read=100, max_gap=8, holes=holes)
    assert blocks == [s(0, 2), s(6, 2)]


def test_boundary_forces_new_block():
    boundaries = {("holding", 4)}
    blocks = plan_blocks([s(0, 2), s(4, 2)], max_read=100, max_gap=8, boundaries=boundaries)
    assert blocks == [s(0, 2), s(4, 2)]


def test_boundary_in_bridge_forces_split():
    # a boundary sitting in the gap that would otherwise be bridged still splits
    boundaries = {("holding", 3)}
    blocks = plan_blocks([s(0, 2), s(6, 2)], max_read=100, max_gap=8, boundaries=boundaries)
    assert blocks == [s(0, 2), s(6, 2)]


def test_boundary_at_block_start_changes_nothing():
    # a boundary that already begins the first block does not split it
    boundaries = {("holding", 0)}
    blocks = plan_blocks([s(0, 2), s(2, 2)], max_read=100, boundaries=boundaries)
    assert blocks == [s(0, 4)]


def test_boundary_other_table_ignored():
    boundaries = {("input", 4)}
    blocks = plan_blocks([s(0, 2), s(4, 2)], max_read=100, max_gap=8, boundaries=boundaries)
    assert blocks == [s(0, 6)]


def test_cap_prevents_merge():
    blocks = plan_blocks([s(0, 60), s(60, 60)], max_read=100)
    assert blocks == [s(0, 60), s(60, 60)]


def test_oversized_span_is_chunked():
    blocks = plan_blocks([s(0, 300)], max_read=125)
    assert blocks == [s(0, 125), s(125, 125), s(250, 50)]


def test_protocol_cap_for_registers():
    blocks = plan_blocks([s(0, 300)], max_read=5000)
    assert all(b.count <= 125 for b in blocks)


def test_protocol_cap_for_bits():
    blocks = plan_blocks([s(0, 3000, table="coil")], max_read=5000)
    assert all(b.count <= 2000 for b in blocks)
    assert len(blocks) == 2


def test_tables_planned_separately():
    blocks = plan_blocks(
        [s(0, 2), s(2, 2, table="input"), s(0, 1, table="coil")],
        max_read=100,
        max_gap=8,
    )
    assert set(blocks) == {s(0, 2), s(2, 2, table="input"), s(0, 1, table="coil")}


def test_realistic_meter_layout():
    # 40 float32 sensors at even addresses 0..78 plus a few scattered ones.
    spans = [s(a, 2) for a in range(0, 80, 2)] + [s(100, 2), s(342, 2), s(344, 2)]
    blocks = plan_blocks(spans, max_read=125, max_gap=8)
    # 0..80 merges into one block, 100 close enough? gap 80->100 is 20 > 8.
    assert blocks == [s(0, 80), s(100, 2), s(342, 4)]


def test_spans_in_block():
    spans = [s(0, 2), s(4, 2), s(10, 2)]
    block = s(0, 6)
    assert spans_in_block(block, spans) == [s(0, 2), s(4, 2)]


def test_bridged_addresses():
    spans = [s(0, 2), s(6, 2)]
    block = s(0, 8)
    assert bridged_addresses(block, spans) == {
        ("holding", 2),
        ("holding", 3),
        ("holding", 4),
        ("holding", 5),
    }
