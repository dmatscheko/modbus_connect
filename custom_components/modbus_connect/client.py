"""Thin pymodbus wrapper: one shared connection per gateway or serial port,
with block reads.

No Home Assistant imports; the coordinator owns scheduling, backoff and
caching — this module only moves bytes and normalizes errors.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any, ClassVar

from pymodbus import FramerType
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse

from .models import BIT_TABLES, TABLE_COIL, TABLE_DISCRETE, TABLE_HOLDING, TABLE_INPUT, Span

_LOGGER = logging.getLogger(__name__)

_ILLEGAL_DATA_ADDRESS = 2

# The exceptions that mean a transient connection/transport failure — as opposed
# to a protocol error *response*, which comes back as an ExceptionResponse.
_CONN_ERRORS = (TimeoutError, ModbusException, OSError)

# Connection defaults; device files may raise them (device: timeout / retries /
# request_delay). Seconds per request, in-driver retransmits, and enforced
# silence between two transactions.
DEFAULT_TIMEOUT = 2.0
DEFAULT_RETRIES = 1
DEFAULT_REQUEST_DELAY = 0.0

# Serial line defaults (Modbus's own default is 19200 8E1, but nearly every
# real device ships 9600 8N1)
DEFAULT_BAUDRATE = 9600
DEFAULT_BYTESIZE = 8
DEFAULT_PARITY = "N"
DEFAULT_STOPBITS = 1

_InnerClient = AsyncModbusTcpClient | AsyncModbusSerialClient


def _read_funcs(client: _InnerClient) -> dict[str, Callable[..., Any]]:
    """The table → pymodbus read-method map for a client."""
    return {
        TABLE_HOLDING: client.read_holding_registers,
        TABLE_INPUT: client.read_input_registers,
        TABLE_COIL: client.read_coils,
        TABLE_DISCRETE: client.read_discrete_inputs,
    }


def _exception_code(response: Any) -> int | None:
    """The Modbus exception code if ``response`` is an ExceptionResponse, else None."""
    return response.exception_code if isinstance(response, ExceptionResponse) else None


def _serial_client(
    serial_port: str,
    baudrate: int,
    bytesize: int,
    parity: str,
    stopbits: int,
    timeout: float,
    retries: int,
) -> AsyncModbusSerialClient:
    return AsyncModbusSerialClient(
        serial_port,
        framer=FramerType.RTU,
        baudrate=baudrate,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
        timeout=timeout,
        retries=retries,
    )


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


# The gateway itself reports it could not reach the device: no route to it, or
# the device behind it stayed silent. Both mean "wrong Modbus ID" far more
# often than anything else.
_GATEWAY_EXCEPTIONS = (10, 11)


async def _probe_read(client: _InnerClient, device_id: int, span: Span) -> str | None:
    """Connect and read once; classify the outcome (see async_probe_device)."""
    try:
        try:
            if not await client.connect():
                return "cannot_connect"
        except _CONN_ERRORS:
            return "cannot_connect"
        read = _read_funcs(client)[span.table]
        try:
            response = await read(
                address=span.start, count=span.count, device_id=device_id
            )
        except _CONN_ERRORS:
            return "device_no_answer"
    finally:
        client.close()
    if _exception_code(response) in _GATEWAY_EXCEPTIONS:
        return "device_no_answer"
    return None


async def async_probe_device(
    host: str,
    port: int,
    device_id: int,
    span: Span,
    *,
    framer: str = "socket",
    timeout: float = 5.0,
) -> str | None:
    """Config-flow validation: TCP connect, then one real read from the device.

    Returns None when the device answered — any Modbus response counts, even an
    error response like *illegal data address* proves a device with this ID is
    listening. Returns ``"cannot_connect"`` when no TCP connection came up, and
    ``"device_no_answer"`` when the gateway is reachable but the device stayed
    silent (wrong Modbus ID, or the serial side is down). The returned strings
    are the config flow's error keys.
    """
    client = AsyncModbusTcpClient(
        host, port=port, framer=FramerType(framer), timeout=timeout, retries=1
    )
    return await _probe_read(client, device_id, span)


async def async_probe_serial(
    serial_port: str,
    *,
    baudrate: int = DEFAULT_BAUDRATE,
    bytesize: int = DEFAULT_BYTESIZE,
    parity: str = DEFAULT_PARITY,
    stopbits: int = DEFAULT_STOPBITS,
    timeout: float = 5.0,
) -> bool:
    """Try to open the serial port (config flow validation)."""
    client = _serial_client(
        serial_port, baudrate, bytesize, parity, stopbits, timeout, 0
    )
    try:
        return bool(await client.connect())
    except (TimeoutError, ModbusException, OSError):
        return False
    finally:
        client.close()


async def async_probe_serial_device(
    serial_port: str,
    device_id: int,
    span: Span,
    *,
    baudrate: int = DEFAULT_BAUDRATE,
    bytesize: int = DEFAULT_BYTESIZE,
    parity: str = DEFAULT_PARITY,
    stopbits: int = DEFAULT_STOPBITS,
    timeout: float = 5.0,
) -> str | None:
    """Serial twin of :func:`async_probe_device`, same return values —
    ``"cannot_connect"`` here means the port could not be opened."""
    client = _serial_client(
        serial_port, baudrate, bytesize, parity, stopbits, timeout, 1
    )
    return await _probe_read(client, device_id, span)


class ModbusBlockClient:
    """One shared connection per target — a TCP gateway (host:port) or a local
    serial port — refcounted by config entry."""

    _instances: ClassVar[dict[str, ModbusBlockClient]] = {}

    def __init__(
        self,
        key: str,
        inner: _InnerClient,
        framer: str,
        line: tuple[int, int, str, int] | None = None,
    ) -> None:
        self.key = key
        self.target = key  # human-readable in errors: "host:port" or "/dev/tty..."
        self.framer = framer
        self._line = line  # serial only: (baudrate, bytesize, parity, stopbits)
        self.lock = asyncio.Lock()
        self._client = inner
        self._read_funcs = _read_funcs(self._client)
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
        """Get (or create) the shared client for a TCP gateway."""
        key = f"{host}:{port}"
        client = cls._instances.get(key)
        if client is None:
            inner = AsyncModbusTcpClient(
                host,
                port=port,
                framer=FramerType(framer),
                timeout=DEFAULT_TIMEOUT,
                retries=DEFAULT_RETRIES,
            )
            client = cls(key, inner, framer)
            cls._instances[key] = client
        elif client.framer != framer:
            # One TCP endpoint speaks exactly one framing; a second connection
            # would not help either (many gateways allow a single client).
            _LOGGER.warning(
                "Gateway %s is already connected with %s framing; keeping it. "
                "All entries sharing a gateway must use the same framing",
                client.target,
                client.framer,
            )
        client._register(entry_id, timeout, retries, request_delay)
        return client

    @classmethod
    def acquire_serial(
        cls,
        serial_port: str,
        entry_id: str,
        *,
        baudrate: int = DEFAULT_BAUDRATE,
        bytesize: int = DEFAULT_BYTESIZE,
        parity: str = DEFAULT_PARITY,
        stopbits: int = DEFAULT_STOPBITS,
        timeout: float | None = None,
        retries: int | None = None,
        request_delay: float | None = None,
    ) -> ModbusBlockClient:
        """Get (or create) the shared client for a local serial port."""
        client = cls._instances.get(serial_port)
        line = (baudrate, bytesize, parity, stopbits)
        if client is None:
            inner = _serial_client(
                serial_port, baudrate, bytesize, parity, stopbits,
                DEFAULT_TIMEOUT, DEFAULT_RETRIES,
            )
            client = cls(serial_port, inner, "rtu", line=line)
            cls._instances[serial_port] = client
        elif client._line != line:
            assert client._line is not None
            baud, size, par, stop = client._line
            _LOGGER.warning(
                "Serial port %s is already open at %d baud %d%s%d; keeping it. "
                "All entries sharing a port must use the same line settings",
                client.target,
                baud,
                size,
                par,
                stop,
            )
        client._register(entry_id, timeout, retries, request_delay)
        return client

    def _register(
        self,
        entry_id: str,
        timeout: float | None,
        retries: int | None,
        request_delay: float | None,
    ) -> None:
        self._refs.add(entry_id)
        self._settings[entry_id] = (
            timeout if timeout is not None else DEFAULT_TIMEOUT,
            retries if retries is not None else DEFAULT_RETRIES,
            request_delay if request_delay is not None else DEFAULT_REQUEST_DELAY,
        )
        self._apply_settings()

    def release(self, entry_id: str) -> None:
        """Drop a config entry's reference; close when the last one goes."""
        self._refs.discard(entry_id)
        self._settings.pop(entry_id, None)
        if not self._refs:
            self._instances.pop(self.key, None)
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
        except _CONN_ERRORS:
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
        except _CONN_ERRORS as exc:
            raise ReadError(f"{span}: {exc}") from exc

        if response.isError():
            illegal = _exception_code(response) == _ILLEGAL_DATA_ADDRESS
            raise ReadError(f"{span}: {response}", illegal_address=illegal)

        values: list[int] | list[bool] = (
            response.bits if span.table in BIT_TABLES else response.registers
        )
        if len(values) < span.count:
            raise ReadError(f"{span}: short response ({len(values)} values)")
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
                raise WriteError(f"{Span(TABLE_HOLDING, address, len(words))}: {response}")
        except _CONN_ERRORS as exc:
            raise WriteError(f"{Span(TABLE_HOLDING, address, len(words))}: {exc}") from exc

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
                raise WriteError(f"{Span(TABLE_COIL, address, 1)}: {response}")
        except _CONN_ERRORS as exc:
            raise WriteError(f"{Span(TABLE_COIL, address, 1)}: {exc}") from exc
