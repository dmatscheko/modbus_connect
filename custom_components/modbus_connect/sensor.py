"""Sensor platform (plus duplicate_as_sensor mirrors of writable entities)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ModbusConnectConfigEntry, ModbusConnectCoordinator
from .entity import (
    ModbusConnectEntity,
    ModbusConnectTemplateEntity,
    build_description,
    build_mirror_description,
    build_template_description,
    suggest_entity_id,
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
    entities.append(ModbusConnectReadCountSensor(coordinator))
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


class ModbusConnectReadCountSensor(
    CoordinatorEntity[ModbusConnectCoordinator], SensorEntity
):
    """Diagnostic: Modbus block reads issued in the last refresh.

    Block merging lets one read cover many entities, so this is usually far below
    the entity count. The ``polled_entities`` attribute is how many entities that
    refresh covered and ``read_entities`` the total that poll — the gap is the win.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "reads"
    _attr_translation_key = "reads_per_refresh"
    _attr_icon = "mdi:download-network"

    def __init__(self, coordinator: ModbusConnectCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_reads_per_refresh"
        self._attr_device_info = coordinator.device_info
        suggest_entity_id(self, coordinator, "sensor", "reads_per_refresh")

    @property
    def native_value(self) -> int:
        return self.coordinator.last_read_count

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        return {
            "polled_entities": self.coordinator.last_polled_count,
            "read_entities": self.coordinator.read_entity_count,
        }
