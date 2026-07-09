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
from custom_components.modbus_connect.client import (
    ModbusBlockClient,
    ReadError,
    WriteError,
    async_probe,
)
from custom_components.modbus_connect.models import Span
from custom_components.modbus_connect.planner import plan_blocks
from custom_components.modbus_connect.schema import parse_device

DEVICE_FILE = (
    Path(__file__).parent.parent
    / "custom_components/modbus_connect/device_configs/SDM630.yaml"
)


# Address zones with special server behavior (see fixture below); chosen above
# every address the SDM630 device file actually uses.
NO_FC16_ZONE = 65000  # refuses multi-register writes (FC16); singles work
ERROR_ZONE = 65280  # answers every request with ILLEGAL DATA ADDRESS


@pytest.fixture
async def modbus_server(socket_enabled: None):
    """A zero-filled Modbus/TCP server that records every request.

    Addresses >= ERROR_ZONE answer with exception code 2 (illegal data
    address); FC16 writes to >= NO_FC16_ZONE are refused so the client's
    single-write fallback can be exercised.

    Depends on pytest-socket's ``socket_enabled`` fixture, NOT the
    ``enable_socket`` marker: the marker is honored in pytest-socket's setup
    hook, while the HA test harness disables sockets in its own setup hook —
    which of the two wins depends on plugin registration order, which differs
    between environments. Fixtures run after all setup hooks, so this always
    wins.
    """
    requests: list[tuple[int, int, int]] = []  # (function_code, address, count/value)

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                tid, pid, length, uid = struct.unpack(">HHHB", await reader.readexactly(7))
                pdu = await reader.readexactly(length - 1)
                fc, addr, count = struct.unpack(">BHH", pdu[:5])
                requests.append((fc, addr, count))
                if addr >= ERROR_ZONE or (fc == 16 and addr >= NO_FC16_ZONE):
                    payload = bytes([fc | 0x80, 2])  # ILLEGAL DATA ADDRESS
                elif fc in (3, 4):  # read holding / input registers
                    payload = bytes([fc, count * 2]) + bytes(count * 2)
                elif fc in (1, 2):  # read coils / discrete inputs
                    nbytes = (count + 7) // 8
                    payload = bytes([fc, nbytes]) + bytes(nbytes)
                elif fc in (5, 6, 16):  # writes: echo address and value/count
                    payload = pdu[:5]
                else:
                    payload = bytes([fc | 0x80, 1])  # ILLEGAL FUNCTION
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


async def test_probe(modbus_server):
    port, _ = modbus_server
    assert await async_probe("127.0.0.1", port) is True

    # a port nothing listens on refuses the connection
    closed = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
    free_port = closed.sockets[0].getsockname()[1]
    closed.close()
    await closed.wait_closed()
    assert await async_probe("127.0.0.1", free_port, timeout=1.0) is False


async def test_client_is_shared_and_refcounted(modbus_server):
    port, _ = modbus_server
    a = ModbusBlockClient.acquire("127.0.0.1", port, "entry-a")
    b = ModbusBlockClient.acquire("127.0.0.1", port, "entry-b")
    assert a is b
    a.release("entry-a")
    assert ModbusBlockClient.acquire("127.0.0.1", port, "entry-c") is a
    a.release("entry-b")
    a.release("entry-c")
    assert ModbusBlockClient.acquire("127.0.0.1", port, "entry-d") is not a
    ModbusBlockClient._instances[("127.0.0.1", port)].release("entry-d")


async def test_writes_and_errors(modbus_server):
    port, requests = modbus_server
    client = ModbusBlockClient.acquire("127.0.0.1", port, "e2e-writes")
    try:
        assert await client.ensure_connected()
        async with client.lock:
            # single register -> FC6
            await client.write_registers(1, 100, [7])
            assert requests[-1] == (6, 100, 7)

            # multiple registers -> FC16
            await client.write_registers(1, 200, [1, 2])
            assert requests[-1] == (16, 200, 2)

            # FC16 refused -> falls back to one FC6 per register
            requests.clear()
            await client.write_registers(1, NO_FC16_ZONE, [1, 2])
            assert [r[0] for r in requests] == [16, 6, 6]

            # coil write -> FC5
            await client.write_coil(1, 5, True)
            assert requests[-1][:2] == (5, 5)

            # error zone: reads raise ReadError with the illegal-address flag
            with pytest.raises(ReadError) as excinfo:
                await client.read_block(1, Span("holding", ERROR_ZONE, 2))
            assert excinfo.value.illegal_address

            # error zone: writes raise WriteError (single and fallback path)
            with pytest.raises(WriteError):
                await client.write_registers(1, ERROR_ZONE, [1])
            with pytest.raises(WriteError):
                await client.write_registers(1, ERROR_ZONE, [1, 2])
            with pytest.raises(WriteError):
                await client.write_coil(1, ERROR_ZONE, True)
    finally:
        client.release("e2e-writes")
