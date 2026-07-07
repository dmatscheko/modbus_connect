"""Entity base classes and the EntityDef -> EntityDescription bridge."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorStateClass
from homeassistant.exceptions import ServiceValidationError, TemplateError
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ModbusConnectCoordinator
from .models import BIT_TABLES, TYPE_STRING, EntityDef, TemplateDef
from .schema import DESCRIPTION_CLASSES, description_fields

_LOGGER = logging.getLogger(__name__)


def build_description(
    defn: EntityDef,
    platform: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> EntityDescription:
    """Build the platform's EntityDescription from the validated ha: block.

    With ``platform`` set, fields the target platform does not know are
    silently dropped (used for duplicate_as_sensor mirrors).
    """
    desc_cls = DESCRIPTION_CLASSES[platform or defn.platform]
    known = description_fields(desc_cls)
    values = {k: v for k, v in defn.ha.items() if k in known}
    if overrides:
        values.update(overrides)
    values.setdefault("name", defn.key.replace("_", " ").capitalize())
    return desc_cls(key=defn.key, **values)


def build_mirror_description(defn: EntityDef) -> EntityDescription:
    """A sensor description mirroring a writable entity (duplicate_as_sensor)."""
    overrides: dict[str, Any] = {"name": f"{defn.ha.get('name') or defn.key} (sensor)"}
    numeric = (
        defn.type != TYPE_STRING
        and defn.table not in BIT_TABLES
        and defn.value_map is None
        and defn.flags is None
    )
    if numeric and "state_class" not in defn.ha:
        overrides["state_class"] = SensorStateClass.MEASUREMENT
    return build_description(defn, platform="sensor", overrides=overrides)


def resolve_on_off(defn: EntityDef, value: Any) -> bool | None:
    """Shared on/off interpretation for switch and binary_sensor."""
    if value is None:
        return None
    if defn.on_value is not None:
        if value == defn.on_value:
            return True
        if defn.off_value is None or value == defn.off_value:
            return False
        return None
    return bool(value)


class ModbusConnectEntity(CoordinatorEntity[ModbusConnectCoordinator]):
    """Base entity: value access, availability, write helper."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ModbusConnectCoordinator,
        defn: EntityDef,
        description: EntityDescription,
        *,
        unique_suffix: str = "",
    ) -> None:
        super().__init__(coordinator)
        self._defn = defn
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry_id}_{defn.key}{unique_suffix}"
        self._attr_device_info = coordinator.device_info

    @property
    def device_value(self) -> Any:
        """The decoded value from the last read, or None.

        Deliberately not named ``value``: NumberEntity and TextEntity define a
        final ``value`` property that converts ``native_value`` for display.
        """
        data = self.coordinator.data
        return None if data is None else data.get(self._defn.key)

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self._defn.platform == "button":
            return True  # buttons do not read
        return self.device_value is not None

    async def _write(self, value: Any) -> None:
        await self.coordinator.async_write(self._defn, value)


def build_template_description(tdef: TemplateDef) -> EntityDescription:
    """Build the EntityDescription for a template: entry."""
    desc_cls = DESCRIPTION_CLASSES[tdef.platform]
    known = description_fields(desc_cls)
    values = {k: v for k, v in tdef.ha.items() if k in known}
    values.setdefault("name", tdef.key.replace("_", " ").capitalize())
    return desc_cls(key=tdef.key, **values)


class ModbusConnectTemplateEntity(CoordinatorEntity[ModbusConnectCoordinator]):
    """Base for template: entities — re-renders on every device poll.

    The device's entity keys are injected as plain Jinja variables (plus a
    ``values`` dict for keys that are not valid identifiers); all normal Home
    Assistant template functions remain available.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ModbusConnectCoordinator,
        tdef: TemplateDef,
        description: EntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._tdef = tdef
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry_id}_{tdef.key}"
        self._attr_device_info = coordinator.device_info
        self._compiled: dict[str, Template] = {}

    def render(self, field: str) -> Any:
        """Render one of the configured templates; None if absent or failing."""
        source = self._tdef.config.get(field)
        if source is None:
            return None
        template = self._compiled.get(field)
        if template is None:
            template = self._compiled[field] = Template(source, self.hass)
        data = self.coordinator.data or {}
        try:
            return template.async_render(
                variables={**data, "values": data}, parse_result=True
            )
        except TemplateError as err:
            _LOGGER.debug("%s: template '%s' failed: %s", self._tdef.key, field, err)
            return None

    def render_number(self, field: str) -> float | None:
        """Render a template that must produce a number."""
        value = self.render(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return None

    async def _run_action(self, name: str, value: Any | None = None) -> None:
        """Execute a configured WriteTarget action.

        Fixed actions write their configured value; mapped actions translate
        the UI value through their map; plain actions write the UI value —
        always through the target entity's codec.
        """
        target = self._tdef.config.get(name)
        if target is None:
            raise ServiceValidationError(
                f"{self._tdef.key} has no '{name}' action",
                translation_domain=DOMAIN,
                translation_key="no_action",
                translation_placeholders={"key": self._tdef.key, "action": name},
            )
        if target.value is not None:
            payload: Any = target.value
        elif target.value_map is not None:
            if str(value) not in target.value_map:
                raise ServiceValidationError(
                    f"{self._tdef.key}: no '{name}' mapping for {value!r}",
                    translation_domain=DOMAIN,
                    translation_key="no_mapping",
                    translation_placeholders={
                        "key": self._tdef.key,
                        "action": name,
                        "value": str(value),
                    },
                )
            payload = target.value_map[str(value)]
        else:
            payload = value
        defn = self.coordinator.entity_defs[target.entity]
        await self.coordinator.async_write(defn, payload)
