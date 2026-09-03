"""Time platform."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity

from .entity import ModbusConnectEntity, platform_setup

# Serialize writes; the gateway handles one transaction at a time.
PARALLEL_UPDATES = 1


class ModbusConnectTime(ModbusConnectEntity, TimeEntity):
    """A writable time-of-day register (HH:MM packed into one register)."""

    @property
    def native_value(self) -> time | None:
        value = self.device_value
        return value if isinstance(value, time) else None

    async def async_set_value(self, value: time) -> None:
        await self._write(value)


async_setup_entry = platform_setup("time", ModbusConnectTime)
