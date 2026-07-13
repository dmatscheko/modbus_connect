"""Text platform."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
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
        ModbusConnectText(coordinator, defn, build_description(defn))
        for defn in coordinator.entities_for("text")
    )


class ModbusConnectText(ModbusConnectEntity, TextEntity):
    """A writable string."""

    @property
    def native_value(self) -> str | None:
        value = self.device_value
        return value if isinstance(value, str) else None

    async def async_set_value(self, value: str) -> None:
        await self._write(value)
