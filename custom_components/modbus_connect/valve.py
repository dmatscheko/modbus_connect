"""Valve platform.

Two shapes, chosen by ``ha.reports_position`` in the device file:

* binary (default): open/close like a switch — ``on_value``/``off_value``
  pick the raw values, a coil writes booleans;
* position: the register holds 0..100 (through the usual conversions), the
  valve is closed at 0 and set_position writes the percentage back.
"""

from __future__ import annotations

from homeassistant.components.valve import ValveEntity, ValveEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ModbusConnectConfigEntry, ModbusConnectCoordinator
from .entity import ModbusConnectEntity, build_description, on_off_payload, resolve_on_off
from .models import EntityDef

# Serialize writes; the gateway handles one transaction at a time.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModbusConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        ModbusConnectValve(
            coordinator,
            defn,
            # ValveEntity requires reports_position to be set; default binary
            build_description(
                defn,
                overrides={
                    "reports_position": bool(defn.ha.get("reports_position"))
                },
            ),
        )
        for defn in coordinator.visible_entities
        if defn.platform == "valve"
    )


class ModbusConnectValve(ModbusConnectEntity, ValveEntity):
    """A valve on a register or coil; see the module docstring."""

    def __init__(
        self,
        coordinator: ModbusConnectCoordinator,
        defn: EntityDef,
        description: EntityDescription,
    ) -> None:
        super().__init__(coordinator, defn, description)
        features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
        if self.reports_position:
            features |= ValveEntityFeature.SET_POSITION
        self._attr_supported_features = features

    @property
    def current_valve_position(self) -> int | None:
        if not self.reports_position:
            return None
        value = self.device_value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return max(0, min(100, round(value)))

    @property
    def is_closed(self) -> bool | None:
        if self.reports_position:
            position = self.current_valve_position
            return None if position is None else position == 0
        is_open = resolve_on_off(self._defn, self.device_value)
        return None if is_open is None else not is_open

    async def async_open_valve(self) -> None:
        if self.reports_position:
            await self._write(100)
        else:
            await self._write(on_off_payload(self._defn, True))

    async def async_close_valve(self) -> None:
        if self.reports_position:
            await self._write(0)
        else:
            await self._write(on_off_payload(self._defn, False))

    async def async_set_valve_position(self, position: int) -> None:
        await self._write(position)
