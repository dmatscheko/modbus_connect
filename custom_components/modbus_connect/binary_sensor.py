"""Binary sensor platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import Entity

from .coordinator import ModbusConnectCoordinator
from .entity import (
    ModbusConnectEntity,
    ModbusConnectMetaEntity,
    ModbusConnectTemplateEntity,
    platform_setup,
    resolve_on_off,
)

# Read-only platform; all data comes through the coordinator.
PARALLEL_UPDATES = 0


class ModbusConnectBinarySensor(ModbusConnectEntity, BinarySensorEntity):
    """A read-only on/off state."""

    @property
    def is_on(self) -> bool | None:
        return resolve_on_off(self._defn, self.device_value)


class ModbusConnectTemplateBinarySensor(ModbusConnectTemplateEntity, BinarySensorEntity):
    """An on/off state computed by a template over the device's values."""

    @property
    def is_on(self) -> bool | None:
        return self.render_bool("state")


class ModbusConnectReadHealthBinarySensor(ModbusConnectMetaEntity, BinarySensorEntity):
    """Health check: on (problem) while a read failed in the last 5 minutes.

    Deliberately a plain polled entity, not a CoordinatorEntity: it must stay
    available exactly when the coordinator is failing, and Home Assistant's
    default 30 s entity poll re-evaluates the window so the problem clears on
    time even when no register value changes. Unchanged polls write no state,
    so a healthy device costs nothing in the recorder.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "read_failures"

    def __init__(self, coordinator: ModbusConnectCoordinator) -> None:
        super().__init__(coordinator, unique_suffix="read_failures", domain="binary_sensor")

    @property
    def is_on(self) -> bool:
        return self._coordinator.read_failures_in_window > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "failed_reads_last_5_min": self._coordinator.read_failures_in_window,
            "failed_reads_total": self._coordinator.failed_read_total,
        }


def _extra_binary_sensors(coordinator: ModbusConnectCoordinator) -> list[Entity]:
    return [ModbusConnectReadHealthBinarySensor(coordinator)]


async_setup_entry = platform_setup(
    "binary_sensor",
    ModbusConnectBinarySensor,
    ModbusConnectTemplateBinarySensor,
    _extra_binary_sensors,
)
