"""Fan platform: template-defined fans backed by Modbus entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import result_as_boolean

from .coordinator import ModbusConnectConfigEntry, ModbusConnectCoordinator
from .entity import ModbusConnectTemplateEntity, build_template_description
from .models import TemplateDef

# Serialize writes; the gateway handles one transaction at a time.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModbusConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        ModbusConnectFan(coordinator, tdef, build_template_description(tdef))
        for tdef in coordinator.visible_templates
        if tdef.platform == "fan"
    )


class ModbusConnectFan(ModbusConnectTemplateEntity, FanEntity):
    """State from 'state'/'percentage'/'preset_mode' templates."""

    def __init__(
        self,
        coordinator: ModbusConnectCoordinator,
        tdef: TemplateDef,
        description: EntityDescription,
    ) -> None:
        super().__init__(coordinator, tdef, description)
        cfg = tdef.config
        features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        if "set_percentage" in cfg:
            features |= FanEntityFeature.SET_SPEED
        if "set_preset_mode" in cfg:
            features |= FanEntityFeature.PRESET_MODE
        self._attr_supported_features = features
        self._attr_preset_modes = cfg.get("preset_modes")

    @property
    def is_on(self) -> bool | None:
        value = self.render("state")
        return None if value is None else result_as_boolean(value)

    @property
    def percentage(self) -> int | None:
        if "percentage" not in self._tdef.config:
            return None
        value = self.render_number("percentage")
        return None if value is None else max(0, min(100, round(value)))

    @property
    def preset_mode(self) -> str | None:
        value = self.render("preset_mode")
        return None if value is None else str(value)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        await self._run_action("turn_on")
        if percentage is not None and "set_percentage" in self._tdef.config:
            await self._run_action("set_percentage", percentage)
        if preset_mode is not None and "set_preset_mode" in self._tdef.config:
            await self._run_action("set_preset_mode", preset_mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._run_action("turn_off")

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self._run_action("turn_off")
        else:
            await self._run_action("set_percentage", percentage)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._run_action("set_preset_mode", preset_mode)
