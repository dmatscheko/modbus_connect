"""Binary sensor platform."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
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

# Read-only platform; all data comes through the coordinator.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModbusConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        ModbusConnectBinarySensor(coordinator, defn, build_description(defn))
        for defn in coordinator.visible_entities
        if defn.platform == "binary_sensor"
    ]
    entities.extend(
        ModbusConnectTemplateBinarySensor(
            coordinator, tdef, build_template_description(tdef)
        )
        for tdef in coordinator.visible_templates
        if tdef.platform == "binary_sensor"
    )
    async_add_entities(entities)


class ModbusConnectBinarySensor(ModbusConnectEntity, BinarySensorEntity):
    """A read-only on/off state."""

    @property
    def is_on(self) -> bool | None:
        return resolve_on_off(self._defn, self.device_value)


class ModbusConnectTemplateBinarySensor(ModbusConnectTemplateEntity, BinarySensorEntity):
    """An on/off state computed by a template over the device's values."""

    @property
    def is_on(self) -> bool | None:
        value = self.render("state")
        return None if value is None else result_as_boolean(value)
