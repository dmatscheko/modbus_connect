"""Fan platform: template-defined fans backed by Modbus entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.helpers.entity import EntityDescription

from .coordinator import ModbusConnectCoordinator
from .entity import ModbusConnectTemplateEntity, platform_setup
from .models import TemplateDef

# Serialize writes; the gateway handles one transaction at a time.
PARALLEL_UPDATES = 1


class ModbusConnectFan(ModbusConnectTemplateEntity, FanEntity):
    """State from 'state'/'percentage'/'preset_mode' templates."""

    def __init__(
        self,
        coordinator: ModbusConnectCoordinator,
        tdef: TemplateDef,
        description: EntityDescription | None = None,
    ) -> None:
        super().__init__(coordinator, tdef, description)
        cfg = tdef.config
        features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        # HA shows percentage/preset only when the feature flag is set, so a
        # read-only template must set it too (like light's brightness); setting
        # without the action raises the clean "has no ... action" error.
        if "set_percentage" in cfg or "percentage" in cfg:
            features |= FanEntityFeature.SET_SPEED
        if "set_preset_mode" in cfg or "preset_mode" in cfg:
            features |= FanEntityFeature.PRESET_MODE
        self._attr_supported_features = features
        self._attr_preset_modes = cfg.get("preset_modes")

    @property
    def is_on(self) -> bool | None:
        return self.render_bool("state")

    @property
    def percentage(self) -> int | None:
        return self.render_level("percentage", 100)

    @property
    def preset_mode(self) -> str | None:
        return self.render_str("preset_mode")

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


async_setup_entry = platform_setup("fan", template_cls=ModbusConnectFan)
