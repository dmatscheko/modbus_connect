"""Light platform: template-defined lights backed by Modbus entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import result_as_boolean

from .coordinator import ModbusConnectConfigEntry
from .entity import ModbusConnectTemplateEntity, build_template_description


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModbusConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        ModbusConnectLight(coordinator, tdef, build_template_description(tdef))
        for tdef in coordinator.device_def.templates
        if tdef.platform == "light"
    )


class ModbusConnectLight(ModbusConnectTemplateEntity, LightEntity):
    """On/off (and optionally brightness 0-255) from templates."""

    def __init__(self, coordinator, tdef, description) -> None:
        super().__init__(coordinator, tdef, description)
        cfg = tdef.config
        dimmable = "brightness" in cfg or "set_brightness" in cfg
        mode = ColorMode.BRIGHTNESS if dimmable else ColorMode.ONOFF
        self._attr_supported_color_modes = {mode}
        self._attr_color_mode = mode

    @property
    def is_on(self) -> bool | None:
        value = self.render("state")
        return None if value is None else result_as_boolean(value)

    @property
    def brightness(self) -> int | None:
        if "brightness" not in self._tdef.config:
            return None
        value = self.render_number("brightness")
        return None if value is None else max(0, min(255, round(value)))

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs and "set_brightness" in self._tdef.config:
            await self._run_action("set_brightness", kwargs[ATTR_BRIGHTNESS])
        else:
            await self._run_action("turn_on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._run_action("turn_off")
