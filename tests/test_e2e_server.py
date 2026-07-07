"""End-to-end efficiency proof against a real Modbus/TCP server socket.

Loads the converted SDM630 device file (85 entities), plans blocks, reads them
through ModbusBlockClient over a real socket, and asserts the whole poll takes
a handful of Modbus transactions instead of one per entity.

The server is a minimal raw asyncio implementation (answers zeros) so the test
counts wire transactions exactly and does not depend on pymodbus server APIs.
"""

import asyncio
import struct
from pathlib import Path

import pytest
import yaml

from custom_components.modbus_connect import codec
from custom_components.modbus_connect.client import ModbusBlockClient
from custom_components.modbus_connect.planner import plan_blocks
from custom_components.modbus_connect.schema import parse_device

DEVICE_FILE = (
    Path(__file__).parent.parent
    / "custom_components/modbus_connect/device_configs/SDM630.yaml"
)


@pytest.fixture
async def modbus_server():
    """A zero-filled Modbus/TCP server that records every request."""
    requests: list[tuple[int, int, int]] = []  # (function_code, address, count)

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                tid, pid, length, uid = struct.unpack(">HHHB", await reader.readexactly(7))
                pdu = await reader.readexactly(length - 1)
                fc, addr, count = struct.unpack(">BHH", pdu[:5])
                requests.append((fc, addr, count))
                if fc in (3, 4):  # read holding / input registers
                    payload = bytes([fc, count * 2]) + bytes(count * 2)
                else:  # read coils / discrete inputs
                    nbytes = (count + 7) // 8
                    payload = bytes([fc, nbytes]) + bytes(nbytes)
                writer.write(struct.pack(">HHHB", tid, pid, len(payload) + 1, uid) + payload)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    yield port, requests
    server.close()
    await server.wait_closed()


@pytest.mark.enable_socket
async def test_sdm630_polls_in_few_transactions(modbus_server):
    port, requests = modbus_server

    with DEVICE_FILE.open(encoding="utf-8") as fh:
        device = parse_device(yaml.safe_load(fh), filename="SDM630.yaml")
    spans = {e.span for e in device.entities if e.platform != "button"}
    entity_count = len(spans)
    assert entity_count > 50  # this is the point of using the SDM630

    client = ModbusBlockClient.acquire("127.0.0.1", port, "e2e-test")
    try:
        assert await client.ensure_connected()

        # 1) With the device's own (conservative, converted) read limits.
        blocks = plan_blocks(spans, max_read=device.max_read, max_gap=device.max_gap)
        cache: dict[tuple[str, int], int] = {}
        async with client.lock:
            for block in blocks:
                values = await client.read_block(1, block)
                for i, addr in enumerate(range(block.start, block.end)):
                    cache[(block.table, addr)] = values[i]

        assert len(requests) == len(blocks)  # one wire transaction per planned block
        assert len(blocks) < entity_count / 2  # at least 2x fewer round trips

        # every entity decodes from the sparse cache (server returns zeros)
        for defn in device.entities:
            raw = [cache[(defn.table, a)] for a in range(defn.address, defn.address + defn.count)]
            codec.decode(defn, raw)

        # 2) With max_register_read: 100 as a user would configure it.
        requests.clear()
        blocks_100 = plan_blocks(spans, max_read=100, max_gap=8)
        async with client.lock:
            for block in blocks_100:
                await client.read_block(1, block)

        assert len(requests) == len(blocks_100)
        assert len(blocks_100) <= 8, (
            f"{entity_count} entities should need at most 8 transactions, "
            f"got {len(blocks_100)}: {blocks_100}"
        )
    finally:
        client.release("e2e-test")
