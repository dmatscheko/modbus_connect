"""Polling coordinator: plans block reads, caches raw registers, decodes values."""

from __future__ import annotations

import logging
import struct
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import codec
from .client import ModbusBlockClient, ReadError, WriteError
from .const import (
    CONF_PREFIX,
    CONF_SLAVE_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_BACKOFF_SECONDS,
    OPTION_SCAN_INTERVAL,
)
from .models import TABLE_COIL, DeviceDef, EntityDef, Span
from .planner import bridged_addresses, plan_blocks, spans_in_block

_LOGGER = logging.getLogger(__name__)

type ModbusConnectConfigEntry = ConfigEntry[ModbusConnectCoordinator]


class ModbusConnectCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """One coordinator per configured device (gateway + slave id).

    Each refresh collects the address spans of all entities that are due,
    merges them into as few Modbus reads as possible, stores the raw words in
    a sparse cache and decodes every due entity from it. ``data`` maps entity
    key -> decoded value (``None`` = unreadable, entity unavailable).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ModbusConnectConfigEntry,
        client: ModbusBlockClient,
        device: DeviceDef,
    ) -> None:
        self.client = client
        self.device_def = device
        self.slave_id: int = entry.data[CONF_SLAVE_ID]
        self.entry_id = entry.entry_id

        base: int = (
            entry.options.get(OPTION_SCAN_INTERVAL)
            or device.scan_interval
            or DEFAULT_SCAN_INTERVAL
        )
        self._readers = [e for e in device.entities if e.platform != "button"]
        self.entity_defs = {e.key: e for e in device.entities}
        self._interval_for = {e.key: e.scan_interval or base for e in self._readers}
        self._tick: int = min([base, *self._interval_for.values()])
        self._next_due: dict[str, float] = dict.fromkeys(self._interval_for, 0.0)
        self._holes: set[tuple[str, int]] = set()
        self._cache: dict[tuple[str, int], int | bool] = {}
        self._consecutive_failures = 0

        # The prefix drives entity ids; the name is the device/entry title.
        # Old entries stored their device name in CONF_PREFIX.
        self.entity_id_prefix: str = entry.data.get(CONF_PREFIX) or ""
        name = (
            entry.data.get(CONF_NAME)
            or self.entity_id_prefix
            or f"{device.manufacturer} {device.model}"
        )
        # HA's device-info card has no free-form rows, so fold the connection
        # (host:port and Modbus id) into model_id — it renders right after
        # the model as "<model> (<host:port · ID N>)".
        connection = f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]} · ID {self.slave_id}"
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=name,
            manufacturer=device.manufacturer,
            model=device.model,
            model_id=connection,
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {self.device_info['name']}",
            update_interval=timedelta(seconds=self._tick),
        )

    # --- device info ----------------------------------------------------------

    def apply_device_info(self) -> None:
        """Fold firmware/hardware/serial into the device info.

        The ``device:`` block may template these from register values (usually
        ``internal`` ones). Rendered once from the first read, before entities —
        and thus the device registry entry — are created.
        """
        if (v := self._render_info(self.device_def.sw_version)) is not None:
            self.device_info["sw_version"] = v
        if (v := self._render_info(self.device_def.hw_version)) is not None:
            self.device_info["hw_version"] = v
        if (v := self._render_info(self.device_def.serial_number)) is not None:
            self.device_info["serial_number"] = v

    def _render_info(self, source: str | None) -> str | None:
        """Render one device-info template; None if absent, failing, or still
        referencing an unread (None) register."""
        if source is None:
            return None
        data = self.data or {}
        try:
            value = Template(source, self.hass).async_render(
                variables={**data, "values": data}, parse_result=False
            )
        except TemplateError as err:
            _LOGGER.debug("%s: device-info template %r failed: %s", self.name, source, err)
            return None
        value = str(value).strip()
        return value if value and "None" not in value else None

    # --- reading -------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        now = time.monotonic()
        due = [e for e in self._readers if self._next_due[e.key] <= now]
        data: dict[str, Any] = dict(self.data) if self.data else {}
        if not due:
            return data

        spans = {e.span for e in due}
        blocks = plan_blocks(
            spans,
            max_read=self.device_def.max_read,
            max_gap=self.device_def.max_gap,
            holes=self._holes,
        )
        ok_blocks = 0
        async with self.client.lock:
            if not await self.client.ensure_connected():
                self._register_failure()
                raise UpdateFailed(
                    f"cannot connect to gateway {self.client.host}:{self.client.port}"
                )
            for block in blocks:
                ok_blocks += await self._read_with_fallback(block, spans)

        if not ok_blocks:
            self._register_failure()
            raise UpdateFailed(f"device {self.slave_id} did not answer any read")
        self._register_success()

        for defn in due:
            value = self._decode(defn)
            data[defn.key] = self._postprocess(defn, data.get(defn.key), value)
            self._next_due[defn.key] = now + self._interval_for[defn.key]
        return data

    async def _read_with_fallback(self, block: Span, spans: set[Span]) -> int:
        """Read one block; on failure retry its spans without gap bridging.

        Returns 1 if at least something was read, else 0. If the block only
        failed because of bridged filler addresses, remember those as holes so
        future plans avoid them.
        """
        try:
            self._store(block, await self.client.read_block(self.slave_id, block))
            return 1
        except ReadError as err:
            _LOGGER.debug("Block %s failed (%s), retrying unbridged", block, err)

        needed = spans_in_block(block, spans)
        sub_blocks = plan_blocks(needed, max_read=self.device_def.max_read)
        if sub_blocks == [block]:
            self._clear(block)
            _LOGGER.debug("Unbridged read %s failed too", block)
            return 0

        all_ok = True
        any_ok = False
        for sub in sub_blocks:
            try:
                self._store(sub, await self.client.read_block(self.slave_id, sub))
                any_ok = True
            except ReadError as err:
                self._clear(sub)
                all_ok = False
                _LOGGER.debug("Fallback read %s failed: %s", sub, err)

        if any_ok and all_ok:
            new_holes = bridged_addresses(block, needed)
            if new_holes:
                self._holes |= new_holes
                _LOGGER.info(
                    "%s: device rejects %d bridged filler address(es) in the %s table; "
                    "not bridging them again",
                    self.name,
                    len(new_holes),
                    block.table,
                )
        return 1 if any_ok else 0

    def _store(self, block: Span, values: list[int] | list[bool]) -> None:
        for i, addr in enumerate(range(block.start, block.end)):
            self._cache[(block.table, addr)] = values[i]

    def _clear(self, block: Span) -> None:
        for addr in range(block.start, block.end):
            self._cache.pop((block.table, addr), None)

    def _decode(self, defn: EntityDef) -> Any:
        raw = [
            self._cache.get((defn.table, a))
            for a in range(defn.address, defn.address + defn.count)
        ]
        if any(v is None for v in raw):
            return None
        try:
            return codec.decode(defn, raw)  # type: ignore[arg-type]
        except (codec.CodecError, ValueError, struct.error) as err:
            _LOGGER.debug("Decoding %s failed: %s", defn.key, err)
            return None

    def _postprocess(self, defn: EntityDef, old: Any, new: Any) -> Any:
        """Value sanity filters: max_change spike rejection, never_resets guard."""
        if (
            new is None
            or old is None
            or isinstance(new, (bool, str))
            or not isinstance(new, (int, float))
            or not isinstance(old, (int, float))
        ):
            return new
        if defn.max_change is not None and abs(new - old) > defn.max_change:
            _LOGGER.debug(
                "%s: change %s -> %s exceeds max_change %s, keeping old value",
                defn.key,
                old,
                new,
                defn.max_change,
            )
            return old
        if defn.never_resets and new < old:
            return old
        return new

    # --- backoff ---------------------------------------------------------------

    def _register_failure(self) -> None:
        self._consecutive_failures += 1
        delay = min(self._tick * 2**self._consecutive_failures, MAX_BACKOFF_SECONDS)
        self.update_interval = timedelta(seconds=max(self._tick, delay))

    def _register_success(self) -> None:
        if self._consecutive_failures:
            self._consecutive_failures = 0
            self.update_interval = timedelta(seconds=self._tick)

    # --- writing ---------------------------------------------------------------

    async def async_write(self, defn: EntityDef, value: Any) -> None:
        """Encode and write a value, then read it back to confirm."""
        confirmed: Any = None
        try:
            async with self.client.lock:
                if not await self.client.ensure_connected():
                    raise HomeAssistantError(
                        f"Cannot connect to gateway {self.client.host}:{self.client.port}",
                        translation_domain=DOMAIN,
                        translation_key="cannot_connect",
                        translation_placeholders={
                            "host": self.client.host,
                            "port": str(self.client.port),
                        },
                    )
                current_raw: int | None = None
                if defn.mask is not None and defn.read_modify_write:
                    raw = await self.client.read_block(self.slave_id, defn.span)
                    current_raw = int(raw[0])
                payload = codec.encode(defn, value, current_raw=current_raw)
                if defn.table == TABLE_COIL:
                    await self.client.write_coil(self.slave_id, defn.address, bool(payload))
                else:
                    assert isinstance(payload, list)
                    await self.client.write_registers(self.slave_id, defn.address, payload)
                if defn.platform != "button":
                    self._store(
                        defn.span, await self.client.read_block(self.slave_id, defn.span)
                    )
                    confirmed = self._decode(defn)
        except (ReadError, WriteError, codec.CodecError) as err:
            raise HomeAssistantError(
                f"Writing {defn.key} failed: {err}",
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"key": defn.key, "error": str(err)},
            ) from err

        if defn.platform != "button":
            data = dict(self.data) if self.data else {}
            data[defn.key] = confirmed
            self.async_set_updated_data(data)
