"""Number platform."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity

from .entity import ModbusConnectEntity, ModbusConnectTemplateEntity, platform_setup

# Serialize writes; the gateway handles one transaction at a time.
PARALLEL_UPDATES = 1


class ModbusConnectNumber(ModbusConnectEntity, NumberEntity):
    """A writable numeric value."""

    @property
    def native_value(self) -> float | None:
        value = self.device_value
        return value if isinstance(value, (int, float)) else None

    async def async_set_native_value(self, value: float) -> None:
        await self._write(value)


class ModbusConnectTemplateNumber(ModbusConnectTemplateEntity, NumberEntity):
    """A numeric value from a template with a configured write action."""

    @property
    def native_value(self) -> float | None:
        return self.render_number("state")

    async def async_set_native_value(self, value: float) -> None:
        await self._run_action("set_value", value)


async_setup_entry = platform_setup("number", ModbusConnectNumber, ModbusConnectTemplateNumber)
