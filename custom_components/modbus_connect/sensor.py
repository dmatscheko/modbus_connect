"""Sensor platform (plus duplicate_as_sensor mirrors of writable entities)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
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
    init_meta_entity,
)
from .models import TemplateDef

# Read-only platform; all data comes through the coordinator.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModbusConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for defn in coordinator.visible_entities:
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
        (
            ModbusConnectIntegralSensor(coordinator, tdef, build_template_description(tdef))
            if tdef.config.get("integrate")
            else ModbusConnectTemplateSensor(coordinator, tdef, build_template_description(tdef))
        )
        for tdef in coordinator.templates_for("sensor")
    )
    entities.append(ModbusConnectReadCountSensor(coordinator))
    entities.append(ModbusConnectFailedReadsSensor(coordinator))
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


class ModbusConnectIntegralSensor(ModbusConnectTemplateEntity, RestoreSensor):
    """A template whose rendered watts are integrated into kilowatt-hours.

    For values the device offers no native energy counter for, the ``state``
    template yields instantaneous power and each coordinator refresh advances a
    Riemann sum (``integrate: trapezoidal|left|right``) — a dashboard-ready
    energy total without a manual Integral helper. Sampling rides the
    coordinator's per-refresh hook, not the listener updates: with
    ``always_update=False`` a listener only fires when some value *changed*,
    but a constant 50 W accumulates energy all the same. The total survives
    restarts; intervals where the source is unavailable (or HA was down) are
    skipped, never interpolated.
    """

    def __init__(
        self,
        coordinator: ModbusConnectCoordinator,
        tdef: TemplateDef,
        description: EntityDescription,
    ) -> None:
        super().__init__(coordinator, tdef, description)
        self._method: str = tdef.config["integrate"]
        self._total = 0.0
        self._last_sample: tuple[float, float] | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        data = await self.async_get_last_sensor_data()
        if data is not None and isinstance(data.native_value, (int, float)):
            self._total = float(data.native_value)
        self.async_on_remove(
            self.coordinator.async_add_refresh_callback(self._on_refresh)
        )
        self._advance(self.coordinator.data)  # seed; the restart gap adds nothing

    @callback
    def _on_refresh(self, data: dict[str, Any]) -> None:
        """Sample every refresh (success implied) and publish the new total."""
        self._advance(data)
        self.async_write_ha_state()

    def _advance(self, data: dict[str, Any] | None) -> None:
        value = self.render_number("state", data)
        if value is None:  # source gap: drop the interval rather than interpolate
            self._last_sample = None
            return
        now = self.coordinator.monotonic_time()
        if self._last_sample is not None:
            then, previous = self._last_sample
            if now > then:
                power = {
                    "trapezoidal": (previous + value) / 2,
                    "left": previous,
                    "right": value,
                }[self._method]
                self._total += power * (now - then) / 3_600_000  # W·s -> kWh
        self._last_sample = (now, value)

    @callback
    def _handle_coordinator_update(self) -> None:
        # Failures arrive here (the refresh hook fires only on success): drop
        # the open interval — outages are skipped, never interpolated.
        if not self.coordinator.last_update_success:
            self._last_sample = None
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float:
        return round(self._total, 3)


class ModbusConnectReadCountSensor(
    CoordinatorEntity[ModbusConnectCoordinator], SensorEntity
):
    """Diagnostic: Modbus block reads a full refresh issues.

    Block merging lets one read cover many entities, so this sits well below the
    ``read_entities`` attribute (the total that poll) — the gap is the merge win.
    It reports the full-refresh figure, which is stable (it moves only when the
    read plan does), so it stays near-silent in the recorder rather than churning
    every cycle; the live per-cycle read and poll counts are in Download
    Diagnostics. Deliberately carries no ``state_class`` — a read gauge has no
    meaningful long-term statistics, and omitting it avoids the 5-minute
    statistics writes.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "reads"
    _attr_translation_key = "reads_per_refresh"

    def __init__(self, coordinator: ModbusConnectCoordinator) -> None:
        super().__init__(coordinator)
        init_meta_entity(
            self, coordinator, unique_suffix="reads_per_refresh", domain="sensor"
        )

    @property
    def native_value(self) -> int:
        return self.coordinator.full_refresh_read_count

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        return {"read_entities": self.coordinator.read_entity_count}


class ModbusConnectFailedReadsSensor(SensorEntity):
    """Diagnostic: failed read transactions since the entry was (re)loaded.

    The ever-increasing companion to the "Read failures" problem indicator —
    chart it or alert on its rate. A plain polled entity (see the binary
    sensor's docstring): available during outages, catches up within one 30 s
    poll, and writes state only when the count actually moved. Deliberately no
    ``state_class``: that would add 5-minute statistics writes for a value that
    should stay at 0.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "reads"
    _attr_translation_key = "failed_reads"

    def __init__(self, coordinator: ModbusConnectCoordinator) -> None:
        self._coordinator = coordinator
        init_meta_entity(
            self, coordinator, unique_suffix="failed_reads", domain="sensor"
        )

    @property
    def native_value(self) -> int:
        return self._coordinator.failed_read_total
