"""Climate platform: template-defined thermostats backed by Modbus entities."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ModbusConnectConfigEntry
from .entity import ModbusConnectTemplateEntity, build_template_description

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModbusConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        ModbusConnectClimate(coordinator, tdef, build_template_description(tdef))
        for tdef in coordinator.device_def.templates
        if tdef.platform == "climate"
    )


class ModbusConnectClimate(ModbusConnectTemplateEntity, ClimateEntity):
    """A thermostat whose state comes from templates over the device's values
    and whose actions write to the device's Modbus entities."""

    def __init__(self, coordinator, tdef, description) -> None:
        super().__init__(coordinator, tdef, description)
        cfg = tdef.config
        self._attr_temperature_unit = cfg.get(
            "temperature_unit", UnitOfTemperature.CELSIUS
        )
        if "min_temp" in cfg:
            self._attr_min_temp = cfg["min_temp"]
        if "max_temp" in cfg:
            self._attr_max_temp = cfg["max_temp"]
        if "temp_step" in cfg:
            self._attr_target_temperature_step = cfg["temp_step"]

        self._attr_hvac_modes = [
            HVACMode(m) for m in cfg.get("hvac_modes", [HVACMode.HEAT])
        ]
        features = ClimateEntityFeature(0)
        if "set_temperature" in cfg:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if "set_hvac_mode" in cfg and HVACMode.OFF in self._attr_hvac_modes:
            features |= ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        self._attr_supported_features = features

    @property
    def current_temperature(self) -> float | None:
        return self.render_number("current_temperature")

    @property
    def target_temperature(self) -> float | None:
        return self.render_number("target_temperature")

    @property
    def hvac_mode(self) -> HVACMode | None:
        value = self.render("hvac_mode")
        if value is None:
            return None
        try:
            return HVACMode(str(value).lower())
        except ValueError:
            _LOGGER.debug("%s: hvac_mode template returned %r", self._tdef.key, value)
            return None

    @property
    def hvac_action(self) -> HVACAction | None:
        value = self.render("hvac_action")
        if value is None:
            return None
        try:
            return HVACAction(str(value).lower())
        except ValueError:
            _LOGGER.debug("%s: hvac_action template returned %r", self._tdef.key, value)
            return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            await self._run_action("set_temperature", temperature)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self._run_action("set_hvac_mode", hvac_mode)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        for mode in self._attr_hvac_modes:
            if mode != HVACMode.OFF:
                await self.async_set_hvac_mode(mode)
                return
