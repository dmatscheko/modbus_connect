#!/usr/bin/env python3
"""Standalone Modbus/TCP debugging client for device-file authors.

Talks to a gateway directly (no Home Assistant involved) to answer the
questions that come up while writing or fixing a device YAML file:

- does the gateway answer, and is the device id right?     -> probe
- what is in these registers, and how do they decode?      -> read
- does writing this value work, and over which function?   -> write
- which addresses does the device actually serve?          -> scan

``scan`` also emits the two planner hints the integration understands, ready
to paste into a device file: addresses the device refuses (``bad_addresses:``)
and in-block boundaries every read must start at (``split_before:``).

Examples:
  python3 support/modbus_cli.py --host my-gateway probe
  python3 support/modbus_cli.py --host my-gateway --device-id 20 read holding 1
  python3 support/modbus_cli.py --host my-gateway read input 0x0610 --count 2
  python3 support/modbus_cli.py --host my-gateway write 5 300
  python3 support/modbus_cli.py --host my-gateway write 5 300 --multiple
  python3 support/modbus_cli.py --host my-gateway write 3 on --coil
  python3 support/modbus_cli.py --host my-gateway scan holding --end 199
  python3 support/modbus_cli.py --host my-gateway --debug read holding 0

Needs only pymodbus (``pip install pymodbus``, or run from the repo venv).
``--debug`` logs every Modbus frame on the wire.
"""

from __future__ import annotations

import argparse
import logging
import struct
import sys
import time
from collections.abc import Iterable, Sequence
from typing import NamedTuple

from pymodbus import pymodbus_apply_logging_config
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse

BIT_TABLES = ("coil", "discrete")
TABLES = ("holding", "input", *BIT_TABLES)

# Modbus exception codes -> what they mean for the person debugging.
EXCEPTION_NAMES = {
    1: "illegal function (device does not support this request type)",
    2: "illegal data address (device does not serve this register)",
    3: "illegal data value",
    4: "device failure",
    5: "acknowledge (long-running command accepted)",
    6: "device busy",
    8: "memory parity error",
    10: "gateway path unavailable (gateway cannot route to the device)",
    11: "gateway target failed to respond (device behind the gateway is silent)",
}


class ReadResult(NamedTuple):
    values: list[int] | list[bool] | None
    error: str | None = None
    # Modbus exception code when the device answered with an error frame —
    # unlike a timeout, that still proves the device is alive.
    exception: int | None = None


class Client:
    """One sync pymodbus client plus per-table read functions and error mapping."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.host: str = args.host
        self.port: int = args.port
        self.device_id: int = args.device_id
        self._client = ModbusTcpClient(
            args.host, port=args.port, timeout=args.timeout, retries=args.retries
        )
        self._read_funcs = {
            "holding": self._client.read_holding_registers,
            "input": self._client.read_input_registers,
            "coil": self._client.read_coils,
            "discrete": self._client.read_discrete_inputs,
        }

    def connect(self) -> bool:
        return bool(self._client.connect())

    def close(self) -> None:
        self._client.close()

    def read(self, table: str, address: int, count: int) -> ReadResult:
        try:
            rr = self._read_funcs[table](
                address=address, count=count, device_id=self.device_id
            )
        except ModbusException as exc:
            return ReadResult(None, str(exc))
        if rr.isError():
            code = rr.exception_code if isinstance(rr, ExceptionResponse) else None
            return ReadResult(None, _describe(rr), code)
        values = rr.bits if table in BIT_TABLES else rr.registers
        return ReadResult(values[:count])

    def write_registers(self, address: int, words: list[int], *, multiple: bool) -> str | None:
        """FC6 for a single word, FC16 for several (or when forced); None on success."""
        try:
            if len(words) == 1 and not multiple:
                rr = self._client.write_register(
                    address=address, value=words[0], device_id=self.device_id
                )
            else:
                rr = self._client.write_registers(
                    address=address, values=words, device_id=self.device_id
                )
        except ModbusException as exc:
            return str(exc)
        return _describe(rr) if rr.isError() else None

    def write_coil(self, address: int, value: bool) -> str | None:
        try:
            rr = self._client.write_coil(
                address=address, value=value, device_id=self.device_id
            )
        except ModbusException as exc:
            return str(exc)
        return _describe(rr) if rr.isError() else None


def _describe(response: object) -> str:
    if isinstance(response, ExceptionResponse):
        code = response.exception_code
        return f"exception {code}: {EXCEPTION_NAMES.get(code, 'unknown')}"
    return str(response)


def _auto_int(text: str) -> int:
    return int(text, 0)  # accepts decimal and 0x hex


def _parse_coil_value(text: str) -> bool:
    lowered = text.lower()
    if lowered in ("1", "on", "true"):
        return True
    if lowered in ("0", "off", "false"):
        return False
    raise SystemExit(f"not a coil value: {text!r} (use on/off)")


def _parse_word(text: str) -> int:
    value = _auto_int(text)
    if not -0x8000 <= value <= 0xFFFF:
        raise SystemExit(f"register word out of range: {text} (use -32768..65535)")
    return value & 0xFFFF  # negatives are written two's-complement


def _format_ranges(addresses: Iterable[int]) -> str:
    runs: list[list[int]] = []
    for a in sorted(addresses):
        if runs and a == runs[-1][1] + 1:
            runs[-1][1] = a
        else:
            runs.append([a, a])
    return ", ".join(f"{s}-{e}" if s != e else f"{s}" for s, e in runs) or "none"


def decoded_views(regs: Sequence[int]) -> list[tuple[str, str]]:
    """Common multi-register interpretations, labeled like device-file types.

    The plain labels assume the Modbus default (big-endian words); the
    ``swap: word`` variants show what a word-swapped device would mean.
    """
    views: list[tuple[str, str]] = []
    if len(regs) in (2, 4):
        bits = 16 * len(regs)
        float_fmt = ">f" if len(regs) == 2 else ">d"
        for suffix, words in (("", list(regs)), (" (swap: word)", list(reversed(regs)))):
            raw = struct.pack(f">{len(words)}H", *words)
            views.append((f"uint{bits}{suffix}", str(int.from_bytes(raw, "big"))))
            views.append((f"int{bits}{suffix}", str(int.from_bytes(raw, "big", signed=True))))
            views.append((f"float{bits}{suffix}", repr(struct.unpack(float_fmt, raw)[0])))
    if len(regs) >= 2:
        raw = struct.pack(f">{len(regs)}H", *regs)
        views.append(("string", "".join(chr(b) if 32 <= b < 127 else "·" for b in raw)))
    return views


# --- commands -----------------------------------------------------------------


def cmd_probe(client: Client, args: argparse.Namespace) -> int:
    started = time.perf_counter()
    if not client.connect():
        print(f"cannot connect to {client.host}:{client.port}")
        return 1
    elapsed = (time.perf_counter() - started) * 1000
    print(f"connected to {client.host}:{client.port} in {elapsed:.0f} ms")
    result = client.read("holding", 0, 1)
    if result.values is not None:
        print(f"device {client.device_id} answers (holding register 0 = {result.values[0]})")
    elif result.exception is not None:
        # an exception frame is still an answer from the device
        print(f"device {client.device_id} answers ({result.error})")
    else:
        print(f"device {client.device_id} did not answer: {result.error} (wrong --device-id?)")
        return 2
    return 0


def cmd_read(client: Client, args: argparse.Namespace) -> int:
    result = client.read(args.table, args.address, args.count)
    if result.values is None:
        print(f"read {args.table}@{args.address}+{args.count} failed: {result.error}")
        return 2
    if args.table in BIT_TABLES:
        for i, bit in enumerate(result.values):
            print(f"{args.address + i:>6}  {'ON' if bit else 'off'}")
        return 0
    regs = [int(v) for v in result.values]
    for i, word in enumerate(regs):
        line = f"{args.address + i:>6}  0x{word:04X}  {word:>5}"
        if word >= 0x8000:
            line += f"  (int16: {word - 0x10000})"
        print(line)
    for label, text in decoded_views(regs):
        print(f"{label:>22}: {text}")
    return 0


def cmd_write(client: Client, args: argparse.Namespace) -> int:
    if args.coil:
        if len(args.values) != 1:
            raise SystemExit("--coil writes exactly one value")
        value = _parse_coil_value(args.values[0])
        error = client.write_coil(args.address, value)
        if error:
            print(f"write coil@{args.address} failed: {error}")
            return 2
        print(f"wrote coil@{args.address} = {'ON' if value else 'off'} (FC5)")
        readback = client.read("coil", args.address, 1)
    else:
        words = [_parse_word(v) for v in args.values]
        fc = "FC16" if len(words) > 1 or args.multiple else "FC6"
        error = client.write_registers(args.address, words, multiple=args.multiple)
        if error:
            print(f"write holding@{args.address}+{len(words)} failed: {error}")
            return 2
        print(f"wrote holding@{args.address} = {words} ({fc})")
        readback = client.read("holding", args.address, len(args.values))
    if readback.values is not None:
        print(f"read back: {readback.values}")
    else:
        print(f"read back failed: {readback.error} (write-only register?)")
    return 0


def cmd_scan(client: Client, args: argparse.Namespace) -> int:
    if args.end < args.start:
        raise SystemExit("--end must be >= --start")
    print(
        f"scanning {args.table} {args.start}..{args.end} as device {client.device_id}, "
        f"blocks of {args.block}"
    )
    readable: set[int] = set()
    refused: dict[int, str] = {}
    boundaries: list[int] = []
    silent_chunks = 0
    for chunk_start in range(args.start, args.end + 1, args.block):
        count = min(args.block, args.end + 1 - chunk_start)
        block = client.read(args.table, chunk_start, count)
        if block.values is not None:
            readable.update(range(chunk_start, chunk_start + count))
            silent_chunks = 0
            continue
        if block.exception is None:
            # a transport error, not a device answer: retrying every single
            # address of a silent device would only stack up timeouts
            silent_chunks += 1
            if silent_chunks >= 3:
                print(f"aborting: no answer for 3 blocks in a row ({block.error})")
                return 2
            continue
        silent_chunks = 0
        # the device rejected the block: read one by one to find the culprits
        chunk_ok: list[int] = []
        for address in range(chunk_start, chunk_start + count):
            single = client.read(args.table, address, 1)
            if single.values is not None:
                readable.add(address)
                chunk_ok.append(address)
            else:
                refused[address] = single.error or "unknown"
        if len(chunk_ok) == count and count > 1:
            # every register answers alone but not as one read: a boundary
            # lies inside; grow spans to find each address a read must start at
            boundaries.extend(
                _find_boundaries(client, args.table, chunk_start, chunk_start + count - 1)
            )

    print(f"\nreadable:   {_format_ranges(readable)}")
    by_reason: dict[str, list[int]] = {}
    for address, reason in refused.items():
        by_reason.setdefault(reason, []).append(address)
    for reason, addresses in sorted(by_reason.items()):
        print(f"refused:    {_format_ranges(addresses)}  ({reason})")
    if boundaries:
        print(f"boundaries: reads must start fresh at {_format_ranges(boundaries)}")

    # planner hints, in device-file syntax; only gaps between readable
    # registers matter (everything past the register map is just the map's end)
    if readable:
        low, high = min(readable), max(readable)
        gaps = sorted(a for a in refused if low < a < high)
        if gaps or boundaries:
            print("\ndevice-file hints:")
            if gaps:
                print(f"  bad_addresses:\n    {args.table}: {gaps}")
            if boundaries:
                print(f"  split_before:\n    {args.table}: {sorted(boundaries)}")
    return 0


def _find_boundaries(client: Client, table: str, start: int, end: int) -> list[int]:
    """Every address in ``start..end`` reads alone but the whole block does not:
    find each address where a read spanning it fails, i.e. must begin a block."""
    found: list[int] = []
    run_start = start
    length = 2
    while run_start + length - 1 <= end:
        if client.read(table, run_start, length).values is None:
            boundary = run_start + length - 1
            found.append(boundary)
            run_start = boundary
            length = 2
        else:
            length += 1
    return found


# --- entry point ----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Debug Modbus/TCP devices: probe, read (with decoded views), "
        "write, and scan for readable registers.",
        epilog=__doc__.split("Examples:")[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--host", required=True, help="gateway hostname or IP address")
    parser.add_argument("--port", type=int, default=502, help="gateway TCP port (default 502)")
    parser.add_argument(
        "--device-id", "--id", type=_auto_int, default=1,
        help="Modbus unit/slave id of the device behind the gateway (default 1)",
    )
    parser.add_argument("--timeout", type=float, default=2.0, help="seconds per request")
    parser.add_argument(
        "--retries", type=int, default=0,
        help="pymodbus retries per request (default 0: see every failure)",
    )
    parser.add_argument("--debug", action="store_true", help="log every Modbus frame")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("probe", help="connect and check that the device answers")
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("read", help="read registers or bits, with decoded views")
    p.add_argument("table", choices=TABLES)
    p.add_argument("address", type=_auto_int, help="first address (decimal or 0x hex)")
    p.add_argument("--count", type=_auto_int, default=1, help="how many to read")
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("write", help="write holding register(s) or one coil")
    p.add_argument("address", type=_auto_int)
    p.add_argument(
        "values", nargs="+",
        help="register word(s), decimal or 0x hex — or on/off with --coil",
    )
    p.add_argument(
        "--multiple", action="store_true",
        help="force FC16 even for a single word (some devices require it)",
    )
    p.add_argument("--coil", action="store_true", help="write a coil (FC5) instead")
    p.set_defaults(func=cmd_write)

    p = sub.add_parser(
        "scan", help="find readable addresses; emits bad_addresses/split_before hints"
    )
    p.add_argument("table", choices=TABLES)
    p.add_argument("--start", type=_auto_int, default=0, help="first address (default 0)")
    p.add_argument("--end", type=_auto_int, required=True, help="last address, inclusive")
    p.add_argument(
        "--block", type=_auto_int, default=8,
        help="addresses per read, like max_register_read (default 8)",
    )
    p.set_defaults(func=cmd_scan)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.debug:
        pymodbus_apply_logging_config(logging.DEBUG)
    client = Client(args)
    try:
        # probe times its own connect; every other command needs one up front
        if args.func is not cmd_probe and not client.connect():
            print(f"cannot connect to {client.host}:{client.port}")
            return 1
        return int(args.func(client, args))
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
