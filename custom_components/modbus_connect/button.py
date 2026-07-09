"""Button platform: pressing writes a configured value."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
        ModbusConnectButton(coordinator, defn, build_description(defn))
        for defn in coordinator.visible_entities
        if defn.platform == "button"
    )


class ModbusConnectButton(ModbusConnectEntity, ButtonEntity):
    """Writes ``write_value`` when pressed; never reads."""

    async def async_press(self) -> None:
        await self._write(self._defn.write_value)
