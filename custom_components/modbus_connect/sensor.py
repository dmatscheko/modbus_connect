"""Sensor platform (plus duplicate_as_sensor mirrors of writable entities)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import ModbusConnectConfigEntry
from .entity import (
    ModbusConnectEntity,
    ModbusConnectTemplateEntity,
    build_description,
    build_mirror_description,
    build_template_description,
)

# Read-only platform; all data comes through the coordinator.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModbusConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for defn in coordinator.device_def.entities:
        if defn.platform == "sensor":
            entities.append(ModbusConnectSensor(coordinator, defn, build_description(defn)))
        elif defn.duplicate_as_sensor:
            entities.append(
                ModbusConnectSensor(
                    coordinator,
                    defn,
                    build_mirror_description(defn),
                    unique_suffix="_sensor",
                    domain="sensor",
                )
            )
    entities.extend(
        ModbusConnectTemplateSensor(coordinator, tdef, build_template_description(tdef))
        for tdef in coordinator.device_def.templates
        if tdef.platform == "sensor"
    )
    async_add_entities(entities)


class ModbusConnectSensor(ModbusConnectEntity, SensorEntity):
    """A read-only value."""

    @property
    def native_value(self) -> StateType:
        value = self.device_value
        if isinstance(value, (str, int, float)) or value is None:
            return value
        return str(value)


class ModbusConnectTemplateSensor(ModbusConnectTemplateEntity, SensorEntity):
    """A sensor computed by a template over the device's values."""

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        value = self.render("state")
        if isinstance(value, (str, int, float, date, datetime, Decimal)) or value is None:
            return value
        return str(value)
