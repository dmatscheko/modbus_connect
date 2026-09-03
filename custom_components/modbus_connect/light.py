"""Light platform: template-defined lights backed by Modbus entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.helpers.entity import EntityDescription

from .coordinator import ModbusConnectCoordinator
from .entity import ModbusConnectTemplateEntity, clamp_round, platform_setup
from .models import TemplateDef

# Serialize writes; the gateway handles one transaction at a time.
PARALLEL_UPDATES = 1


class ModbusConnectLight(ModbusConnectTemplateEntity, LightEntity):
    """On/off (and optionally brightness 0-255) from templates."""

    def __init__(
        self,
        coordinator: ModbusConnectCoordinator,
        tdef: TemplateDef,
        description: EntityDescription | None = None,
    ) -> None:
        super().__init__(coordinator, tdef, description)
        cfg = tdef.config
        dimmable = "brightness" in cfg or "set_brightness" in cfg
        mode = ColorMode.BRIGHTNESS if dimmable else ColorMode.ONOFF
        self._attr_supported_color_modes = {mode}
        self._attr_color_mode = mode

    @property
    def is_on(self) -> bool | None:
        return self.render_bool("state")

    @property
    def brightness(self) -> int | None:
        if "brightness" not in self._tdef.config:
            return None
        value = self.render_number("brightness")
        return None if value is None else clamp_round(value, 255)

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs and "set_brightness" in self._tdef.config:
            await self._run_action("set_brightness", kwargs[ATTR_BRIGHTNESS])
        else:
            await self._run_action("turn_on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._run_action("turn_off")


async_setup_entry = platform_setup("light", template_cls=ModbusConnectLight)
