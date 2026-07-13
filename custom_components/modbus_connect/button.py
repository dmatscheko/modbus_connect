"""Button platform: pressing writes a configured value."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ModbusConnectConfigEntry, ModbusConnectCoordinator
from .entity import ModbusConnectEntity, build_description, init_meta_entity

_LOGGER = logging.getLogger(__name__)

# Serialize writes; the gateway handles one transaction at a time.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModbusConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[ButtonEntity] = [
        ModbusConnectButton(coordinator, defn, build_description(defn))
        for defn in coordinator.entities_for("button")
    ]
    entities.append(ModbusConnectRemoveHiddenButton(coordinator))
    async_add_entities(entities)


class ModbusConnectButton(ModbusConnectEntity, ButtonEntity):
    """Writes ``write_value`` when pressed; never reads."""

    async def async_press(self) -> None:
        await self._write(self._defn.write_value)


class ModbusConnectRemoveHiddenButton(ButtonEntity):
    """Deletes the registry entries this entry no longer provides.

    Disabling a group keeps the hidden entities' registry rows (grayed out as
    "no longer provided") so renames, areas, and enabled/disabled choices
    survive re-enabling. Users who instead want them gone press this: it
    removes every row not currently provided — group-hidden entities and stale
    keys from an earlier device file — and touches nothing that is provided,
    so customizations on live (even user-disabled) entities are safe.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False
    _attr_translation_key = "remove_hidden"

    def __init__(self, coordinator: ModbusConnectCoordinator) -> None:
        self._coordinator = coordinator
        init_meta_entity(
            self, coordinator, unique_suffix="remove_hidden_entities", domain="button"
        )

    async def async_press(self) -> None:
        registry = er.async_get(self.hass)
        provided = self._coordinator.provided_unique_ids
        stale = [
            reg_entry
            for reg_entry in er.async_entries_for_config_entry(
                registry, self._coordinator.entry_id
            )
            if reg_entry.unique_id not in provided
        ]
        for reg_entry in stale:
            registry.async_remove(reg_entry.entity_id)
        _LOGGER.info(
            "%s: removed %d no-longer-provided entities from the registry",
            self._coordinator.name,
            len(stale),
        )
