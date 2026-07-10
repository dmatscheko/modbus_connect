"""Thin pymodbus wrapper: shared per-gateway connection with block reads.

No Home Assistant imports; the coordinator owns scheduling, backoff and
caching — this module only moves bytes and normalizes errors.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, ClassVar

from pymodbus import FramerType
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse

from .models import BIT_TABLES, TABLE_COIL, TABLE_DISCRETE, TABLE_HOLDING, TABLE_INPUT, Span

_LOGGER = logging.getLogger(__name__)

_ILLEGAL_DATA_ADDRESS = 2

# Connection defaults; device files may raise them (device: timeout / retries /
# request_delay). Seconds per request, in-driver retransmits, and enforced
# silence between two transactions.
DEFAULT_TIMEOUT = 2.0
DEFAULT_RETRIES = 1
DEFAULT_REQUEST_DELAY = 0.0


class ReadError(Exception):
    """A read request failed."""

    def __init__(self, message: str, *, illegal_address: bool = False) -> None:
        super().__init__(message)
        self.illegal_address = illegal_address


class WriteError(Exception):
    """A write request failed."""


async def async_probe(host: str, port: int, timeout: float = 5.0) -> bool:
    """Try to open a TCP connection to the gateway (config flow validation)."""
    client = AsyncModbusTcpClient(host, port=port, timeout=timeout, retries=0)
    try:
        return bool(await client.connect())
    except (TimeoutError, ModbusException, OSError):
        return False
    finally:
        client.close()


class ModbusBlockClient:
    """One shared TCP connection per gateway (host:port), refcounted by entry."""

    _instances: ClassVar[dict[tuple[str, int], ModbusBlockClient]] = {}

    def __init__(self, host: str, port: int, framer: str = "socket") -> None:
        self.host = host
        self.port = port
        self.framer = framer
        self.lock = asyncio.Lock()
        self._client = AsyncModbusTcpClient(
            host,
            port=port,
            framer=FramerType(framer),
            timeout=DEFAULT_TIMEOUT,
            retries=DEFAULT_RETRIES,
        )
        self._read_funcs = {
            TABLE_HOLDING: self._client.read_holding_registers,
            TABLE_INPUT: self._client.read_input_registers,
            TABLE_COIL: self._client.read_coils,
            TABLE_DISCRETE: self._client.read_discrete_inputs,
        }
        self._refs: set[str] = set()
        # Per-entry (timeout, retries, request_delay) requests; the effective
        # values are the maxima — see _apply_settings.
        self._settings: dict[str, tuple[float, int, float]] = {}
        self._request_delay = DEFAULT_REQUEST_DELAY
        self._last_io = 0.0  # monotonic end time of the last wire transaction

    # --- instance sharing ------------------------------------------------------

    @classmethod
    def acquire(
        cls,
        host: str,
        port: int,
        entry_id: str,
        *,
        framer: str = "socket",
        timeout: float | None = None,
        retries: int | None = None,
        request_delay: float | None = None,
    ) -> ModbusBlockClient:
        """Get (or create) the shared client for a gateway."""
        client = cls._instances.get((host, port))
        if client is None:
            client = cls(host, port, framer)
            cls._instances[(host, port)] = client
        elif client.framer != framer:
            # One TCP endpoint speaks exactly one framing; a second connection
            # would not help either (many gateways allow a single client).
            _LOGGER.warning(
                "Gateway %s:%s is already connected with %s framing; keeping it. "
                "All entries sharing a gateway must use the same framing",
                host,
                port,
                client.framer,
            )
        client._refs.add(entry_id)
        client._settings[entry_id] = (
            timeout if timeout is not None else DEFAULT_TIMEOUT,
            retries if retries is not None else DEFAULT_RETRIES,
            request_delay if request_delay is not None else DEFAULT_REQUEST_DELAY,
        )
        client._apply_settings()
        return client

    def release(self, entry_id: str) -> None:
        """Drop a config entry's reference; close when the last one goes."""
        self._refs.discard(entry_id)
        self._settings.pop(entry_id, None)
        if not self._refs:
            self._instances.pop((self.host, self.port), None)
            self._client.close()
        else:
            self._apply_settings()  # a released entry no longer pins the maxima

    def _apply_settings(self) -> None:
        """Make the shared connection meet every entry's needs (max wins).

        pymodbus reads both values per request; there is no public setter, so
        this writes the attributes the transaction manager actually consults
        rather than recreating the (shared, possibly in-use) connection.
        """
        settings = self._settings.values()
        timeout = max((s[0] for s in settings), default=DEFAULT_TIMEOUT)
        retries = max((s[1] for s in settings), default=DEFAULT_RETRIES)
        self._request_delay = max((s[2] for s in settings), default=DEFAULT_REQUEST_DELAY)
        self._client.comm_params.timeout_connect = timeout
        self._client.ctx.retries = retries

    # --- I/O ---------------------------------------------------------------------

    async def ensure_connected(self) -> bool:
        if self._client.connected:
            return True
        try:
            return bool(await self._client.connect())
        except (TimeoutError, ModbusException, OSError):
            return False

    async def _transact(self, func: Any, **kwargs: Any) -> Any:
        """One wire transaction; enforces the configured inter-request silence.

        Serialized by the caller-held lock, so waiting here delays every
        queued transaction — which is the point: picky RS-485 gateways need
        the bus quiet between any two frames, including retries of ours.
        """
        if self._request_delay > 0:
            wait = self._last_io + self._request_delay - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
        try:
            return await func(**kwargs)
        finally:
            self._last_io = time.monotonic()

    async def read_block(self, device_id: int, span: Span) -> list[int] | list[bool]:
        """Read one planned block; caller holds ``self.lock``."""
        try:
            response = await self._transact(
                self._read_funcs[span.table],
                address=span.start,
                count=span.count,
                device_id=device_id,
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

        values: list[int] | list[bool] = (
            response.bits if span.table in BIT_TABLES else response.registers
        )
        if len(values) < span.count:
            raise ReadError(
                f"{span.table}@{span.start}+{span.count}: short response "
                f"({len(values)} values)"
            )
        # Bit responses are padded to full bytes; trim to what was asked for.
        return values[: span.count]

    async def write_registers(
        self, device_id: int, address: int, words: list[int], *, multiple: bool = False
    ) -> None:
        """Write holding registers; caller holds ``self.lock``.

        Uses FC6 for a single register, FC16 for several — or for one when
        ``multiple`` is set, which some devices require even for a single
        register (SolaX WRITE_MULTISINGLE). A genuine multi-register FC16 that
        fails falls back to register-by-register FC6 for devices without FC16.
        """
        try:
            if len(words) == 1 and not multiple:
                response = await self._transact(
                    self._client.write_register,
                    address=address,
                    value=words[0],
                    device_id=device_id,
                )
            else:
                response = await self._transact(
                    self._client.write_registers,
                    address=address,
                    values=words,
                    device_id=device_id,
                )
                if response.isError() and len(words) > 1:
                    _LOGGER.debug(
                        "FC16 failed at %s, retrying as single writes", address
                    )
                    for i, word in enumerate(words):
                        response = await self._transact(
                            self._client.write_register,
                            address=address + i,
                            value=word,
                            device_id=device_id,
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
            response = await self._transact(
                self._client.write_coil,
                address=address,
                value=value,
                device_id=device_id,
            )
            if response.isError():
                raise WriteError(f"coil@{address}: {response}")
        except (TimeoutError, ModbusException, OSError) as exc:
            raise WriteError(f"coil@{address}: {exc}") from exc
