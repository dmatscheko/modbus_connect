"""Shared test doubles: the fake gateway client, clock, and device factories.

One FakeClient serves every suite — the single place to update when the real
ModbusBlockClient interface moves. It combines the (table, address) value
store and release tracking the setup tests need with the failure injection
and read/write recording the coordinator tests need.
"""

import asyncio
from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.modbus_connect.client import ReadError
from custom_components.modbus_connect.const import CONF_FILENAME, CONF_SLAVE_ID, DOMAIN
from custom_components.modbus_connect.coordinator import ModbusConnectCoordinator
from custom_components.modbus_connect.models import BIT_TABLES, DeviceDef, EntityDef, Span


class FakeTime:
    """Controllable monotonic clock."""

    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now


class FakeClient:
    """Duck-typed ModbusBlockClient backed by a per-table value dict.

    ``registers`` seeds holding registers (the common case); other tables are
    seeded through ``values[(table, address)]``. Reads, writes, and releases
    are recorded; ``fail_spans`` / ``fail_addresses`` / ``illegal`` inject
    read errors.
    """

    def __init__(
        self, registers: dict[int, int] | None = None, *, target: str = "127.0.0.1:502"
    ) -> None:
        self.target = target
        self.lock = asyncio.Lock()
        self.values: dict[tuple[str, int], int | bool] = {
            ("holding", address): value for address, value in (registers or {}).items()
        }
        self.reads: list[Span] = []
        self.written: list[tuple[int, list[int]]] = []
        self.write_multiple_flags: list[bool] = []
        self.released: list[str] = []
        self.fail_spans: set[Span] = set()
        self.fail_addresses: set[int] = set()
        self.illegal = False  # fail with the device's explicit illegal-address answer
        self.connected_ok = True

    async def ensure_connected(self) -> bool:
        return self.connected_ok

    async def read_block(self, device_id: int, span: Span) -> list[int] | list[bool]:
        self.reads.append(span)
        if span in self.fail_spans or any(
            span.start <= a < span.end for a in self.fail_addresses
        ):
            raise ReadError(f"fail {span}", illegal_address=self.illegal)
        default: int | bool = False if span.table in BIT_TABLES else 0
        return [
            self.values.get((span.table, a), default) for a in range(span.start, span.end)
        ]

    async def write_registers(
        self, device_id: int, address: int, words: list[int], *, multiple: bool = False
    ) -> None:
        self.written.append((address, words))
        self.write_multiple_flags.append(multiple)
        for i, word in enumerate(words):
            self.values[("holding", address + i)] = word

    async def write_coil(self, device_id: int, address: int, value: bool) -> None:
        self.written.append((address, [int(value)]))
        self.values[("coil", address)] = value

    def release(self, entry_id: str) -> None:
        self.released.append(entry_id)


def make_device(
    *entities: EntityDef, max_read: int = 100, max_gap: int = 8, **kwargs: Any
) -> DeviceDef:
    return DeviceDef(
        manufacturer="Acme",
        model="X1",
        entities=entities,
        max_read=max_read,
        max_gap=max_gap,
        filename="test.yaml",
        **kwargs,
    )


def sensor(key: str, address: int, **kwargs: Any) -> EntityDef:
    kwargs.setdefault("platform", "sensor")
    return EntityDef(key=key, address=address, **kwargs)


async def make_coordinator(
    hass, device: DeviceDef, client: FakeClient, monkeypatch, faketime, options=None
):
    monkeypatch.setattr("custom_components.modbus_connect.coordinator.time", faketime)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "127.0.0.1", "port": 502, CONF_SLAVE_ID: 1, CONF_FILENAME: "test.yaml"},
        options=options or {},
    )
    entry.add_to_hass(hass)
    return ModbusConnectCoordinator(hass, entry, client, device)
