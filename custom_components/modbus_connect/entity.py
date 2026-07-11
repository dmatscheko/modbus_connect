"""Entity base classes and the EntityDef -> EntityDescription bridge."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorStateClass
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import ModbusConnectCoordinator, render_over_values
from .models import (
    BIT_TABLES,
    TYPE_STRING,
    TYPE_TIME,
    EntityDef,
    SwitchTarget,
    TemplateDef,
    WriteTarget,
)
from .schema import DESCRIPTION_CLASSES, description_fields


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
        defn.type not in (TYPE_STRING, TYPE_TIME)  # a time mirror's state is "HH:MM:SS"
        and defn.table not in BIT_TABLES
        and defn.value_map is None
        and defn.flags is None
    )
    if numeric and "state_class" not in defn.ha:
        overrides["state_class"] = SensorStateClass.MEASUREMENT
    return build_description(defn, platform="sensor", overrides=overrides)


def suggest_entity_id(
    entity: Entity, coordinator: ModbusConnectCoordinator, domain: str, key: str
) -> None:
    """Suggest ``<domain>.<prefix>_<key>`` as the entity id.

    Only applies when the config entry has an entity-id prefix, and only on
    first registration — renames done by the user stick.
    """
    if not coordinator.entity_id_prefix:
        return
    object_id = slugify(f"{coordinator.entity_id_prefix} {key}")
    if object_id:
        entity.entity_id = f"{domain}.{object_id}"


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
        domain: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._defn = defn
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry_id}_{defn.key}{unique_suffix}"
        self._attr_device_info = coordinator.device_info
        suggest_entity_id(
            self, coordinator, domain or defn.platform, f"{defn.key}{unique_suffix}"
        )

    @property
    def device_value(self) -> Any:
        """The decoded value from the last read, or None.

        Deliberately not named ``value``: NumberEntity defines a final
        ``value`` property (``state`` returns it) that converts
        ``native_value`` into the display unit; shadowing it would bypass
        that conversion.
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
        suggest_entity_id(self, coordinator, tdef.platform, tdef.key)

    def render(self, field: str) -> Any:
        """Render one of the configured templates; None if absent or failing."""
        source = self._tdef.config.get(field)
        if source is None:
            return None
        return self._render_source(source, field)

    def _render_source(self, source: str, cache_key: str) -> Any:
        """Render a template string (compiled cache keyed by ``cache_key``)."""
        template = self._compiled.get(cache_key)
        if template is None:
            template = self._compiled[cache_key] = Template(source, self.hass)
        data = self.coordinator.data
        return render_over_values(template, data, key_fn=self.coordinator.key_lookup(data))

    def render_number(self, field: str) -> float | None:
        """Render a template that must produce a number."""
        value = self.render(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return None

    def _resolve_switch(self, name: str, switch: SwitchTarget) -> WriteTarget:
        """Pick a switch action's target by rendering its selector template."""
        selected = self._render_source(switch.selector, f"{name}.by")
        target = switch.cases.get(str(selected)) if selected is not None else None
        if target is None:
            raise ServiceValidationError(
                f"{self._tdef.key}: '{name}' has no case for {selected!r}",
                translation_domain=DOMAIN,
                translation_key="no_case",
                translation_placeholders={
                    "key": self._tdef.key,
                    "action": name,
                    "value": str(selected),
                },
            )
        return target

    async def _run_action(self, name: str, value: Any | None = None) -> None:
        """Execute a configured write action.

        A switch action first renders its selector to pick a case. Then: fixed
        actions write their configured value; mapped actions translate the UI
        value through their map; plain actions write the UI value — always
        through the target entity's codec.
        """
        target = self._tdef.config.get(name)
        if target is None:
            raise ServiceValidationError(
                f"{self._tdef.key} has no '{name}' action",
                translation_domain=DOMAIN,
                translation_key="no_action",
                translation_placeholders={"key": self._tdef.key, "action": name},
            )
        if isinstance(target, SwitchTarget):
            target = self._resolve_switch(name, target)
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
