"""Repair issues: problems only a change to the device file (or its choice) can fix.

Each issue id starts with the config entry id, so one entry's issues are cleared
together on setup and unload — they describe runtime state (a quarantine resets
on reload) and are not persisted across restarts.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, QUARANTINE_RETRY_SECONDS
from .models import EntityDef, derive_name


def _quarantine_id(entry_id: str, key: str) -> str:
    return f"{entry_id}_quarantined_{key}"


@callback
def async_clear_entry_issues(hass: HomeAssistant, entry_id: str) -> None:
    """Delete every issue raised for one config entry."""
    for domain, issue_id in list(ir.async_get(hass).issues):
        if domain == DOMAIN and issue_id.startswith(f"{entry_id}_"):
            ir.async_delete_issue(hass, DOMAIN, issue_id)


@callback
def async_report_quarantined(
    hass: HomeAssistant, entry_id: str, device: str, filename: str, defn: EntityDef
) -> None:
    """The device keeps refusing an entity's register: its address is likely wrong."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        _quarantine_id(entry_id, defn.key),
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="register_quarantined",
        translation_placeholders={
            "device": device,
            "entity": str(defn.ha.get("name") or derive_name(defn.key)),
            "key": defn.key,
            "span": str(defn.span),
            "filename": filename,
            "retry_minutes": str(QUARANTINE_RETRY_SECONDS // 60),
        },
    )


@callback
def async_clear_quarantined(hass: HomeAssistant, entry_id: str, key: str) -> None:
    """The register answers again: its issue resolves itself."""
    ir.async_delete_issue(hass, DOMAIN, _quarantine_id(entry_id, key))


@callback
def async_report_invalid_device_file(
    hass: HomeAssistant, entry_id: str, title: str, filename: str, error: str
) -> None:
    """The entry's device file does not load, so the device is not set up."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{entry_id}_invalid_device_file",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="invalid_device_file",
        translation_placeholders={"title": title, "filename": filename, "error": error},
    )
