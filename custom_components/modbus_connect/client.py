"""Thin pymodbus wrapper: shared per-gateway connection with block reads.

No Home Assistant imports; the coordinator owns scheduling, backoff and
caching — this module only moves bytes and normalizes errors.
"""

from __future__ import annotations

import asyncio
import logging
from typing import ClassVar

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse

from .models import BIT_TABLES, TABLE_COIL, TABLE_DISCRETE, TABLE_HOLDING, TABLE_INPUT, Span

_LOGGER = logging.getLogger(__name__)

_ILLEGAL_DATA_ADDRESS = 2


class ReadError(Exception):
    """A read request failed."""

    def __init__(self, message: str, *, illegal_address: bool = False) -> None:
        super().__init__(message)
        self.illegal_address = illegal_address


class WriteError(Exception):
    """A write request failed."""


class ModbusBlockClient:
    """One shared TCP connection per gateway (host:port), refcounted by entry."""

    _instances: ClassVar[dict[tuple[str, int], ModbusBlockClient]] = {}

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.lock = asyncio.Lock()
        self._client = AsyncModbusTcpClient(host, port=port, timeout=2.0, retries=1)
        self._refs: set[str] = set()

    # --- instance sharing ------------------------------------------------------

    @classmethod
    def acquire(cls, host: str, port: int, entry_id: str) -> ModbusBlockClient:
        """Get (or create) the shared client for a gateway."""
        client = cls._instances.get((host, port))
        if client is None:
            client = cls(host, port)
            cls._instances[(host, port)] = client
        client._refs.add(entry_id)
        return client

    def release(self, entry_id: str) -> None:
        """Drop a config entry's reference; close when the last one goes."""
        self._refs.discard(entry_id)
        if not self._refs:
            self._instances.pop((self.host, self.port), None)
            self._client.close()

    # --- I/O ---------------------------------------------------------------------

    async def ensure_connected(self) -> bool:
        if self._client.connected:
            return True
        try:
            return bool(await self._client.connect())
        except (TimeoutError, ModbusException, OSError):
            return False

    async def read_block(self, device_id: int, span: Span) -> list[int] | list[bool]:
        """Read one planned block; caller holds ``self.lock``."""
        funcs = {
            TABLE_HOLDING: self._client.read_holding_registers,
            TABLE_INPUT: self._client.read_input_registers,
            TABLE_COIL: self._client.read_coils,
            TABLE_DISCRETE: self._client.read_discrete_inputs,
        }
        try:
            response = await funcs[span.table](
                address=span.start, count=span.count, device_id=device_id
            )
        except (TimeoutError, ModbusException, OSError) as exc:
            raise ReadError(f"{span.table}@{span.start}+{span.count}: {exc}") from exc

        if response.isError():
            illegal = (
                isinstance(response, ExceptionResponse)
                and response.exception_code == _ILLEGAL_DATA_ADDRESS
            )
            raise ReadError(
                f"{span.table}@{span.start}+{span.count}: {response}",
                illegal_address=illegal,
            )

        values = response.bits if span.table in BIT_TABLES else response.registers
        if len(values) < span.count:
            raise ReadError(
                f"{span.table}@{span.start}+{span.count}: short response "
                f"({len(values)} values)"
            )
        # Bit responses are padded to full bytes; trim to what was asked for.
        return values[: span.count]

    async def write_registers(self, device_id: int, address: int, words: list[int]) -> None:
        """Write holding registers; caller holds ``self.lock``.

        Uses FC6 for a single register, FC16 otherwise, and falls back to
        register-by-register FC6 for devices that do not implement FC16.
        """
        try:
            if len(words) == 1:
                response = await self._client.write_register(
                    address=address, value=words[0], device_id=device_id
                )
            else:
                response = await self._client.write_registers(
                    address=address, values=words, device_id=device_id
                )
                if response.isError():
                    _LOGGER.debug(
                        "FC16 failed at %s, retrying as single writes", address
                    )
                    for i, word in enumerate(words):
                        response = await self._client.write_register(
                            address=address + i, value=word, device_id=device_id
                        )
                        if response.isError():
                            break
            if response.isError():
                raise WriteError(f"holding@{address}: {response}")
        except (TimeoutError, ModbusException, OSError) as exc:
            raise WriteError(f"holding@{address}: {exc}") from exc

    async def write_coil(self, device_id: int, address: int, value: bool) -> None:
        """Write one coil; caller holds ``self.lock``."""
        try:
            response = await self._client.write_coil(
                address=address, value=value, device_id=device_id
            )
            if response.isError():
                raise WriteError(f"coil@{address}: {response}")
        except (TimeoutError, ModbusException, OSError) as exc:
            raise WriteError(f"coil@{address}: {exc}") from exc
