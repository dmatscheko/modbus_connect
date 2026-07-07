"""Number platform."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ModbusConnectConfigEntry
from .entity import (
    ModbusConnectEntity,
    ModbusConnectTemplateEntity,
    build_description,
    build_template_description,
)

# Serialize writes; the gateway handles one transaction at a time.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModbusConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = [
        ModbusConnectNumber(coordinator, defn, build_description(defn))
        for defn in coordinator.device_def.entities
        if defn.platform == "number"
    ]
    entities.extend(
        ModbusConnectTemplateNumber(coordinator, tdef, build_template_description(tdef))
        for tdef in coordinator.device_def.templates
        if tdef.platform == "number"
    )
    async_add_entities(entities)


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
