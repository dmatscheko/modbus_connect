"""Write function-code selection and fallback in the pymodbus wrapper."""

import pytest

from custom_components.modbus_connect.client import ModbusBlockClient, WriteError


class _Resp:
    def __init__(self, error: bool) -> None:
        self._error = error

    def isError(self) -> bool:
        return self._error


class _FakeClient:
    """Records write calls; returns an error response per the configured script."""

    def __init__(self, *, fc6_error: bool = False, fc16_error: bool = False) -> None:
        self.calls: list = []
        self._fc6_error = fc6_error
        self._fc16_error = fc16_error

    async def write_register(self, address, value, device_id):
        self.calls.append(("fc6", address, value))
        return _Resp(self._fc6_error)

    async def write_registers(self, address, values, device_id):
        self.calls.append(("fc16", address, values))
        return _Resp(self._fc16_error)


def _client(fake: _FakeClient) -> ModbusBlockClient:
    client = ModbusBlockClient.__new__(ModbusBlockClient)  # skip real connection setup
    client._client = fake  # type: ignore[attr-defined]
    return client


async def test_single_register_uses_fc6():
    fake = _FakeClient()
    await _client(fake).write_registers(1, 103, [40])
    assert fake.calls == [("fc6", 103, 40)]  # FC6 for a single register


async def test_single_register_error_surfaces_directly():
    # No FC16 fallback: a device that answers FC6 with an error (e.g. a locked
    # SolaX returning "device failure") gets that error reported as-is, not
    # masked by a second write to a function code it does not implement.
    fake = _FakeClient(fc6_error=True)
    with pytest.raises(WriteError):
        await _client(fake).write_registers(1, 103, [40])
    assert fake.calls == [("fc6", 103, 40)]  # only FC6 was tried


async def test_multi_register_uses_fc16():
    fake = _FakeClient()
    await _client(fake).write_registers(1, 103, [1, 2])
    assert fake.calls == [("fc16", 103, [1, 2])]


async def test_multi_register_falls_back_to_single_writes():
    # devices without multi-register write get register-by-register FC6
    fake = _FakeClient(fc16_error=True)
    await _client(fake).write_registers(1, 103, [1, 2])
    assert fake.calls == [("fc16", 103, [1, 2]), ("fc6", 103, 1), ("fc6", 104, 2)]


async def test_forced_multiple_single_register_uses_fc16():
    # SolaX WRITE_MULTISINGLE registers need FC16 even for one register
    fake = _FakeClient()
    await _client(fake).write_registers(1, 124, [3], multiple=True)
    assert fake.calls == [("fc16", 124, [3])]


async def test_forced_multiple_does_not_fall_back_to_fc6():
    # a forced single-register FC16 must not silently downgrade to FC6 on error
    fake = _FakeClient(fc16_error=True)
    with pytest.raises(WriteError):
        await _client(fake).write_registers(1, 124, [3], multiple=True)
    assert fake.calls == [("fc16", 124, [3])]
