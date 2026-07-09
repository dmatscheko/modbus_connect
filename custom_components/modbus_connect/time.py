"""Time platform."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ModbusConnectConfigEntry
from .entity import ModbusConnectEntity, build_description

# Serialize writes; the gateway handles one transaction at a time.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModbusConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        ModbusConnectTime(coordinator, defn, build_description(defn))
        for defn in coordinator.device_def.entities
        if defn.platform == "time"
    )


class ModbusConnectTime(ModbusConnectEntity, TimeEntity):
    """A writable time-of-day register (HH:MM packed into one register)."""

    @property
    def native_value(self) -> time | None:
        value = self.device_value
        return value if isinstance(value, time) else None

    async def async_set_value(self, value: time) -> None:
        await self._write(value)
