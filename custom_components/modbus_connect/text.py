"""Text platform."""

from __future__ import annotations

from homeassistant.components.text import TextEntity

from .entity import ModbusConnectEntity, platform_setup

# Serialize writes; the gateway handles one transaction at a time.
PARALLEL_UPDATES = 1


class ModbusConnectText(ModbusConnectEntity, TextEntity):
    """A writable string."""

    @property
    def native_value(self) -> str | None:
        value = self.device_value
        return value if isinstance(value, str) else None

    async def async_set_value(self, value: str) -> None:
        await self._write(value)


async_setup_entry = platform_setup("text", ModbusConnectText)
