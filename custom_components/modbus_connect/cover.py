"""Cover platform: template-defined covers backed by Modbus entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import ATTR_POSITION, CoverEntity, CoverEntityFeature
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
        ModbusConnectCover(coordinator, tdef, build_template_description(tdef))
        for tdef in coordinator.visible_templates
        if tdef.platform == "cover"
    )


class ModbusConnectCover(ModbusConnectTemplateEntity, CoverEntity):
    """State from 'is_closed'/'position' templates; actions write registers."""

    def __init__(
        self,
        coordinator: ModbusConnectCoordinator,
        tdef: TemplateDef,
        description: EntityDescription,
    ) -> None:
        super().__init__(coordinator, tdef, description)
        cfg = tdef.config
        features = CoverEntityFeature(0)
        if "open_cover" in cfg:
            features |= CoverEntityFeature.OPEN
        if "close_cover" in cfg:
            features |= CoverEntityFeature.CLOSE
        if "stop_cover" in cfg:
            features |= CoverEntityFeature.STOP
        if "set_position" in cfg:
            features |= CoverEntityFeature.SET_POSITION
        self._attr_supported_features = features

    @property
    def current_cover_position(self) -> int | None:
        if "position" not in self._tdef.config:
            return None
        value = self.render_number("position")
        return None if value is None else max(0, min(100, round(value)))

    @property
    def is_closed(self) -> bool | None:
        if "is_closed" in self._tdef.config:
            value = self.render("is_closed")
            return None if value is None else result_as_boolean(value)
        position = self.current_cover_position
        return None if position is None else position == 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._run_action("open_cover")

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._run_action("close_cover")

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._run_action("stop_cover")

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        await self._run_action("set_position", kwargs[ATTR_POSITION])
