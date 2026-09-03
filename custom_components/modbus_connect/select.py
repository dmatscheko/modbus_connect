"""Select platform."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import EntityDescription

from .coordinator import ModbusConnectCoordinator
from .entity import ModbusConnectEntity, ModbusConnectTemplateEntity, platform_setup
from .models import EntityDef, TemplateDef

# Serialize writes; the gateway handles one transaction at a time.
PARALLEL_UPDATES = 1


class ModbusConnectSelect(ModbusConnectEntity, SelectEntity):
    """A writable enum backed by the entity's map."""

    def __init__(
        self,
        coordinator: ModbusConnectCoordinator,
        defn: EntityDef,
        description: EntityDescription | None = None,
    ) -> None:
        super().__init__(coordinator, defn, description)
        assert defn.value_map is not None
        self._attr_options = list(defn.value_map.values())

    @property
    def current_option(self) -> str | None:
        value = self.device_value
        return value if isinstance(value, str) else None

    async def async_select_option(self, option: str) -> None:
        await self._write(option)


class ModbusConnectTemplateSelect(ModbusConnectTemplateEntity, SelectEntity):
    """An option list from a template with a configured write action."""

    def __init__(
        self,
        coordinator: ModbusConnectCoordinator,
        tdef: TemplateDef,
        description: EntityDescription | None = None,
    ) -> None:
        super().__init__(coordinator, tdef, description)
        self._attr_options = list(tdef.config["options"])

    @property
    def current_option(self) -> str | None:
        return self.render_str("state")

    async def async_select_option(self, option: str) -> None:
        await self._run_action("select_option", option)


async_setup_entry = platform_setup("select", ModbusConnectSelect, ModbusConnectTemplateSelect)
