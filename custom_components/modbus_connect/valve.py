"""Valve platform.

Two shapes, chosen by ``ha.reports_position`` in the device file:

* binary (default): open/close like a switch — ``on_value``/``off_value``
  pick the raw values, a coil writes booleans;
* position: the register holds 0..100 (through the usual conversions), the
  valve is closed at 0 and set_position writes the percentage back.
"""

from __future__ import annotations

from homeassistant.components.valve import ValveEntity, ValveEntityFeature
from homeassistant.helpers.entity import EntityDescription

from .coordinator import ModbusConnectCoordinator
from .entity import (
    ModbusConnectEntity,
    clamp_round,
    closed_from_position,
    on_off_payload,
    platform_setup,
    resolve_on_off,
)
from .models import EntityDef

# Serialize writes; the gateway handles one transaction at a time.
PARALLEL_UPDATES = 1


class ModbusConnectValve(ModbusConnectEntity, ValveEntity):
    """A valve on a register or coil; see the module docstring."""

    def __init__(
        self,
        coordinator: ModbusConnectCoordinator,
        defn: EntityDef,
        description: EntityDescription | None = None,
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
        return clamp_round(value, 100)

    @property
    def is_closed(self) -> bool | None:
        if self.reports_position:
            return closed_from_position(self.current_valve_position)
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


async_setup_entry = platform_setup("valve", ModbusConnectValve)
