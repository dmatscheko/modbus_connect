"""Climate platform: template-defined thermostats backed by Modbus entities."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, TypeVar

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ModbusConnectConfigEntry, ModbusConnectCoordinator
from .entity import ModbusConnectTemplateEntity, build_template_description
from .models import TemplateDef

_LOGGER = logging.getLogger(__name__)

_HVACEnum = TypeVar("_HVACEnum", bound=Enum)

# Serialize writes; the gateway handles one transaction at a time.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModbusConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        ModbusConnectClimate(coordinator, tdef, build_template_description(tdef))
        for tdef in coordinator.templates_for("climate")
    )


class ModbusConnectClimate(ModbusConnectTemplateEntity, ClimateEntity):
    """A thermostat whose state comes from templates over the device's values
    and whose actions write to the device's Modbus entities."""

    def __init__(
        self,
        coordinator: ModbusConnectCoordinator,
        tdef: TemplateDef,
        description: EntityDescription,
    ) -> None:
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

    def _render_hvac(self, field: str, enum_cls: type[_HVACEnum]) -> _HVACEnum | None:
        """Render a template field onto a closed HVAC enum; None (with a debug
        log) on a value the enum doesn't know."""
        value = self.render(field)
        if value is None:
            return None
        try:
            return enum_cls(str(value).lower())
        except ValueError:
            _LOGGER.debug("%s: %s template returned %r", self._tdef.key, field, value)
            return None

    @property
    def hvac_mode(self) -> HVACMode | None:
        return self._render_hvac("hvac_mode", HVACMode)

    @property
    def hvac_action(self) -> HVACAction | None:
        return self._render_hvac("hvac_action", HVACAction)

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
