"""Switch platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import result_as_boolean

from .const import BASIC_GROUP, OPTION_ENABLED_GROUPS
from .coordinator import ModbusConnectConfigEntry, ModbusConnectCoordinator
from .entity import (
    ModbusConnectEntity,
    ModbusConnectTemplateEntity,
    build_description,
    build_template_description,
    resolve_on_off,
    suggest_entity_id,
)
from .models import BIT_TABLES

# Serialize writes; the gateway handles one transaction at a time.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModbusConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = [
        ModbusConnectSwitch(coordinator, defn, build_description(defn))
        for defn in coordinator.visible_entities
        if defn.platform == "switch"
    ]
    entities.extend(
        ModbusConnectTemplateSwitch(coordinator, tdef, build_template_description(tdef))
        for tdef in coordinator.visible_templates
        if tdef.platform == "switch"
    )
    # Group toggles are integration-level config controls, always present and never
    # themselves group-filtered. The basic group is always on and gets no toggle.
    entities.extend(
        ModbusConnectGroupSwitch(coordinator, entry, group)
        for group in coordinator.all_groups
        if group != BASIC_GROUP
    )
    async_add_entities(entities)


class ModbusConnectSwitch(ModbusConnectEntity, SwitchEntity):
    """A writable on/off state on a coil or holding register."""

    @property
    def is_on(self) -> bool | None:
        return resolve_on_off(self._defn, self.device_value)

    def _payload(self, turn_on: bool) -> Any:
        configured = self._defn.on_value if turn_on else self._defn.off_value
        if configured is not None:
            return configured
        if self._defn.table in BIT_TABLES:
            return turn_on
        return 1 if turn_on else 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._write(self._payload(True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._write(self._payload(False))


class ModbusConnectTemplateSwitch(ModbusConnectTemplateEntity, SwitchEntity):
    """An on/off state from a template with configured write actions."""

    @property
    def is_on(self) -> bool | None:
        value = self.render("state")
        return None if value is None else result_as_boolean(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._run_action("turn_on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._run_action("turn_off")


class ModbusConnectGroupSwitch(SwitchEntity):
    """Config toggle that creates or removes the entities of one group.

    Toggling rewrites the entry's enabled-groups option, which reloads the entry
    and rebuilds the entity set. Hidden entities become "no longer provided" (gray)
    rather than deleted, so the registry keeps the user's customizations and
    restores them when the group is re-enabled. Removed entities also drop out of
    the Modbus read plan.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False
    _attr_translation_key = "group_enable"
    _attr_icon = "mdi:eye-check"

    def __init__(
        self,
        coordinator: ModbusConnectCoordinator,
        entry: ModbusConnectConfigEntry,
        group: str,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._group = group
        self._attr_translation_placeholders = {"group": group}
        self._attr_unique_id = f"{entry.entry_id}_group_{group}"
        self._attr_device_info = coordinator.meta_device_info
        suggest_entity_id(self, coordinator, "switch", f"enable_{group}_entities")

    @property
    def is_on(self) -> bool:
        return self._group in self._coordinator.enabled_groups

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(enabled=False)

    async def _set(self, *, enabled: bool) -> None:
        groups = set(self._coordinator.enabled_groups)
        if enabled:
            groups.add(self._group)
        else:
            groups.discard(self._group)
        if frozenset(groups) == self._coordinator.enabled_groups:
            return
        groups.discard(BASIC_GROUP)  # implicit everywhere, never persisted
        # The entry's update listener (see __init__.py) reloads and rebuilds entities.
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, OPTION_ENABLED_GROUPS: sorted(groups)},
        )
