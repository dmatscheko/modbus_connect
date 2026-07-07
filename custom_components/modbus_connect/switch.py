"""Switch platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import result_as_boolean

from .coordinator import ModbusConnectConfigEntry
from .entity import (
    ModbusConnectEntity,
    ModbusConnectTemplateEntity,
    build_description,
    build_template_description,
    resolve_on_off,
)
from .models import BIT_TABLES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModbusConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = [
        ModbusConnectSwitch(coordinator, defn, build_description(defn))
        for defn in coordinator.device_def.entities
        if defn.platform == "switch"
    ]
    entities.extend(
        ModbusConnectTemplateSwitch(coordinator, tdef, build_template_description(tdef))
        for tdef in coordinator.device_def.templates
        if tdef.platform == "switch"
    )
    async_add_entities(entities)


class ModbusConnectSwitch(ModbusConnectEntity, SwitchEntity):
    """A writable on/off state on a coil or holding register."""

    @property
    def is_on(self) -> bool | None:
        return resolve_on_off(self._defn, self.value)

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
