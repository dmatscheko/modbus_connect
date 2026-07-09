"""Diagnostics support: config, device definition, planning state, and values."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import ModbusConnectConfigEntry

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ModbusConnectConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    device = coordinator.device_def
    data = coordinator.data or {}

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "device": {
            "manufacturer": device.manufacturer,
            "model": device.model,
            "filename": device.filename,
            "max_register_read": device.max_read,
            "max_read_gap": device.max_gap,
            "bad_addresses": sorted(device.bad_addresses),
            "split_before": sorted(device.boundaries),
            "scan_interval": device.scan_interval,
            "min_scan_interval": device.min_scan_interval,
            "entity_count": len(device.entities),
            "template_count": len(device.templates),
            "groups": list(device.group_names),
            "default_groups": list(device.default_groups),
        },
        "polling": {
            "last_update_success": coordinator.last_update_success,
            "enabled_groups": sorted(coordinator.enabled_groups),
            "visible_entity_count": len(coordinator.visible_entities),
            "update_interval": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
            "consecutive_failures": coordinator._consecutive_failures,
            "learned_holes": sorted(coordinator._holes),
            "last_read_count": coordinator.last_read_count,
            "last_polled_count": coordinator.last_polled_count,
            "read_entity_count": coordinator.read_entity_count,
            "failed_read_total": coordinator.failed_read_total,
            "read_failures_in_window": coordinator.read_failures_in_window,
            "failed_reads_by_key": dict(
                sorted(coordinator.failed_reads_by_key.items(), key=lambda kv: -kv[1])
            ),
        },
        "entities": [
            {
                "key": defn.key,
                "platform": defn.platform,
                "table": defn.table,
                "address": defn.address,
                "count": defn.count,
                "type": defn.type,
                "scan_interval": defn.scan_interval,
                "value": data.get(defn.key),
            }
            for defn in device.entities
        ],
        "templates": [
            {"key": tdef.key, "platform": tdef.platform} for tdef in device.templates
        ],
    }
