"""Coordinator behavior tests with a fake client (no network)."""

import asyncio
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.modbus_connect.client import ReadError
from custom_components.modbus_connect.const import (
    CONF_FILENAME,
    CONF_SLAVE_ID,
    DOMAIN,
)
from custom_components.modbus_connect.coordinator import ModbusConnectCoordinator
from custom_components.modbus_connect.models import DeviceDef, EntityDef, Span


class FakeTime:
    """Controllable monotonic clock."""

    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now


class FakeClient:
    """Duck-typed ModbusBlockClient recording every read."""

    host = "127.0.0.1"
    port = 502

    def __init__(self, registers: dict[int, int] | None = None) -> None:
        self.lock = asyncio.Lock()
        self.registers = registers or {}
        self.reads: list[Span] = []
        self.written: list[tuple[int, list[int]]] = []
        self.fail_spans: set[Span] = set()
        self.fail_addresses: set[int] = set()
        self.connected_ok = True

    async def ensure_connected(self) -> bool:
        return self.connected_ok

    async def read_block(self, device_id: int, span: Span) -> list[int]:
        self.reads.append(span)
        if span in self.fail_spans or any(
            span.start <= a < span.end for a in self.fail_addresses
        ):
            raise ReadError(f"fail {span}", illegal_address=True)
        return [self.registers.get(a, 0) for a in range(span.start, span.end)]

    async def write_registers(self, device_id: int, address: int, words: list[int]) -> None:
        self.written.append((address, words))
        for i, w in enumerate(words):
            self.registers[address + i] = w

    async def write_coil(self, device_id: int, address: int, value: bool) -> None:
        self.written.append((address, [int(value)]))


def make_device(*entities: EntityDef, max_read: int = 100, max_gap: int = 8) -> DeviceDef:
    return DeviceDef(
        manufacturer="Acme",
        model="X1",
        entities=entities,
        max_read=max_read,
        max_gap=max_gap,
        filename="test.yaml",
    )


def sensor(key: str, address: int, **kwargs: Any) -> EntityDef:
    kwargs.setdefault("platform", "sensor")
    return EntityDef(key=key, address=address, **kwargs)


async def make_coordinator(hass, device: DeviceDef, client: FakeClient, monkeypatch, faketime):
    monkeypatch.setattr("custom_components.modbus_connect.coordinator.time", faketime)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "127.0.0.1", "port": 502, CONF_SLAVE_ID: 1, CONF_FILENAME: "test.yaml"},
    )
    entry.add_to_hass(hass)
    return ModbusConnectCoordinator(hass, entry, client, device)


async def test_adjacent_entities_one_read(hass, monkeypatch):
    client = FakeClient({0: 100, 1: 200, 2: 300})
    device = make_device(sensor("a", 0), sensor("b", 1), sensor("c", 2))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert client.reads == [Span("holding", 0, 3)]
    assert coordinator.data == {"a": 100, "b": 200, "c": 300}


async def test_scan_interval_buckets(hass, monkeypatch):
    faketime = FakeTime()
    client = FakeClient({0: 1, 50: 2})
    device = make_device(sensor("fast", 0), sensor("slow", 50, scan_interval=300))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, faketime)

    await coordinator.async_refresh()  # both due initially
    assert len(client.reads) == 2  # gap of 49 > max_gap: two blocks

    client.reads.clear()
    faketime.now += 60  # only "fast" (30 s default) is due
    await coordinator.async_refresh()
    assert client.reads == [Span("holding", 0, 1)]
    assert coordinator.data["slow"] == 2  # kept from previous cycle


async def test_bridged_hole_learned(hass, monkeypatch):
    client = FakeClient({0: 1, 1: 2, 6: 3, 7: 4})
    client.fail_addresses = {3}  # device rejects reading address 3
    device = make_device(sensor("a", 0, type="uint32", count=2), sensor("b", 6, type="uint32", count=2))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    await coordinator.async_refresh()
    assert coordinator.last_update_success
    # the bridged block failed, then both entities recovered individually
    assert client.reads == [
        Span("holding", 0, 8),  # bridged read, rejected by the device
        Span("holding", 0, 2),  # unbridged fallback reads
        Span("holding", 6, 2),
    ]
    assert coordinator._holes == {("holding", a) for a in (2, 3, 4, 5)}

    client.reads.clear()
    coordinator._next_due = dict.fromkeys(coordinator._next_due, 0.0)
    await coordinator.async_refresh()
    # planner now avoids the bridge entirely
    assert client.reads == [Span("holding", 0, 2), Span("holding", 6, 2)]


async def test_partial_failure_keeps_other_entities(hass, monkeypatch):
    client = FakeClient({0: 7})
    client.fail_addresses = {50}
    device = make_device(sensor("ok", 0), sensor("broken", 50))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data["ok"] == 7
    assert coordinator.data["broken"] is None  # entity unavailable, device alive


async def test_backoff_on_total_failure(hass, monkeypatch):
    client = FakeClient()
    client.connected_ok = False
    device = make_device(sensor("a", 0))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    base = coordinator.update_interval.total_seconds()

    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    first = coordinator.update_interval.total_seconds()
    await coordinator.async_refresh()
    second = coordinator.update_interval.total_seconds()
    assert first > base
    assert second > first

    client.connected_ok = True
    coordinator._next_due = dict.fromkeys(coordinator._next_due, 0.0)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.update_interval.total_seconds() == pytest.approx(base)


async def test_max_change_and_never_resets(hass, monkeypatch):
    faketime = FakeTime()
    client = FakeClient({0: 100, 1: 500})
    device = make_device(
        sensor("spiky", 0, max_change=10),
        sensor("total", 1, never_resets=True),
    )
    coordinator = await make_coordinator(hass, device, client, monkeypatch, faketime)

    await coordinator.async_refresh()
    assert coordinator.data == {"spiky": 100, "total": 500}

    client.registers[0] = 900  # spike
    client.registers[1] = 3  # counter reset glitch
    faketime.now += 60
    await coordinator.async_refresh()
    assert coordinator.data == {"spiky": 100, "total": 500}

    client.registers[0] = 105  # sane change
    faketime.now += 60
    await coordinator.async_refresh()
    assert coordinator.data["spiky"] == 105


async def test_write_encodes_and_confirms(hass, monkeypatch):
    client = FakeClient({0: 150})
    defn = EntityDef(
        key="setpoint",
        platform="number",
        address=0,
        multiplier=0.1,
        ha={"native_min_value": 0, "native_max_value": 50},
    )
    device = make_device(defn)
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    await coordinator.async_refresh()
    assert coordinator.data["setpoint"] == 15

    await coordinator.async_write(defn, 21.5)
    assert client.written == [(0, [215])]
    assert coordinator.data["setpoint"] == pytest.approx(21.5)  # confirmed by read-back


async def test_masked_write_read_modify_write(hass, monkeypatch):
    client = FakeClient({0: 0x0A5F})
    defn = EntityDef(
        key="nibble",
        platform="number",
        address=0,
        mask=0x00F0,
        read_modify_write=True,
        ha={"native_min_value": 0, "native_max_value": 15},
    )
    device = make_device(defn)
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    await coordinator.async_refresh()

    await coordinator.async_write(defn, 3)
    assert client.written == [(0, [0x0A3F])]  # other bits preserved


async def test_nothing_due_returns_cache(hass, monkeypatch):
    faketime = FakeTime()
    client = FakeClient({0: 5})
    device = make_device(sensor("a", 0))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, faketime)
    await coordinator.async_refresh()
    client.reads.clear()

    await coordinator.async_refresh()  # nothing due yet
    assert client.reads == []
    assert coordinator.data == {"a": 5}


async def test_all_reads_fail_raises(hass, monkeypatch):
    client = FakeClient()
    client.fail_addresses = {0}
    device = make_device(sensor("a", 0))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    await coordinator.async_refresh()
    assert not coordinator.last_update_success


async def test_partial_fallback_learns_no_holes(hass, monkeypatch):
    client = FakeClient({0: 1, 6: 2})
    client.fail_addresses = {6}  # a real entity address fails, not a bridge
    device = make_device(sensor("a", 0), sensor("b", 6))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data == {"a": 1, "b": None}
    assert coordinator._holes == set()


async def test_write_cannot_connect_raises(hass, monkeypatch):
    from homeassistant.exceptions import HomeAssistantError

    client = FakeClient({0: 1})
    defn = EntityDef(
        key="x",
        platform="number",
        address=0,
        ha={"native_min_value": 0, "native_max_value": 10},
    )
    device = make_device(defn)
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    await coordinator.async_refresh()

    client.connected_ok = False
    with pytest.raises(HomeAssistantError, match="Cannot connect"):
        await coordinator.async_write(defn, 5)


async def test_undecodable_value_becomes_none(hass, monkeypatch):
    client = FakeClient({0: 1})
    # count contradicts the type width; decode raises and the value is None
    device = make_device(sensor("broken", 0, type="float32", count=1))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data["broken"] is None
