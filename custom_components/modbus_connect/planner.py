"""Read-block planning: merge entity spans into as few Modbus reads as possible.

Pure functions, no Home Assistant imports.

``plan_blocks`` turns the set of address spans the entities need into a small
list of read requests. Overlapping and adjacent spans always merge; holes of
unused addresses up to ``max_gap`` are bridged (reading a few unneeded
registers is far cheaper than an extra round trip). Blocks never exceed
``max_read`` or the Modbus protocol limit, and never bridge across addresses
that are known to be unreadable (``holes``, learned from failed reads).
"""

from __future__ import annotations

from collections.abc import Iterable

from .models import (
    BIT_TABLES,
    PROTOCOL_MAX_BITS,
    PROTOCOL_MAX_REGISTERS,
    Span,
)

Hole = tuple[str, int]  # (table, address)


def _table_cap(table: str, max_read: int) -> int:
    protocol = PROTOCOL_MAX_BITS if table in BIT_TABLES else PROTOCOL_MAX_REGISTERS
    return max(1, min(max_read, protocol))


def _split(table: str, start: int, end: int, cap: int) -> list[Span]:
    out: list[Span] = []
    while start < end:
        count = min(cap, end - start)
        out.append(Span(table, start, count))
        start += count
    return out


def plan_blocks(
    spans: Iterable[Span],
    *,
    max_read: int,
    max_gap: int = 0,
    holes: frozenset[Hole] | set[Hole] = frozenset(),
) -> list[Span]:
    """Plan the read requests covering all ``spans``."""
    blocks: list[Span] = []
    unique = sorted(set(spans))
    for table in sorted({s.table for s in unique}):
        cap = _table_cap(table, max_read)
        cur_start: int | None = None
        cur_end = 0
        for span in (s for s in unique if s.table == table):
            if cur_start is None:
                cur_start, cur_end = span.start, span.end
                continue
            if span.start <= cur_end:
                bridged: range = range(0)
            else:
                bridged = range(cur_end, span.start)
            fits = max(cur_end, span.end) - cur_start <= cap
            gap_ok = len(bridged) <= max_gap and not any(
                (table, a) in holes for a in bridged
            )
            if fits and gap_ok:
                cur_end = max(cur_end, span.end)
            else:
                blocks.extend(_split(table, cur_start, cur_end, cap))
                cur_start, cur_end = span.start, span.end
        if cur_start is not None:
            blocks.extend(_split(table, cur_start, cur_end, cap))
    return blocks


def spans_in_block(block: Span, spans: Iterable[Span]) -> list[Span]:
    """The needed spans a block was covering (for per-span fallback reads)."""
    return sorted(
        {
            s
            for s in spans
            if s.table == block.table and s.start >= block.start and s.end <= block.end
        }
    )


def bridged_addresses(block: Span, spans: Iterable[Span]) -> set[Hole]:
    """Addresses inside ``block`` that no span needs (bridged filler).

    When a bridged block fails but its individual spans read fine, these are
    the addresses to remember as unreadable holes.
    """
    covered: set[int] = set()
    for s in spans:
        if s.table != block.table:
            continue
        lo, hi = max(s.start, block.start), min(s.end, block.end)
        covered.update(range(lo, hi))
    return {
        (block.table, a) for a in range(block.start, block.end) if a not in covered
    }
