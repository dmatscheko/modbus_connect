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
    OPTION_MIN_SCAN_INTERVAL,
)
from .models import TABLE_COIL, DeviceDef, EntityDef, Span
from .planner import bridged_addresses, plan_blocks, spans_in_block

_LOGGER = logging.getLogger(__name__)

type ModbusConnectConfigEntry = ConfigEntry[ModbusConnectCoordinator]


def render_over_values(
    template: Template, data: dict[str, Any] | None, *, parse_result: bool = True
) -> Any:
    """Render a compiled template over the device's decoded values.

    Each entity key is injected as a plain variable, plus a ``values`` dict for
    keys that are not valid identifiers. Returns None if the template raises.
    This is the one convention shared by the template: section, ``read_register``,
    and the device-info fields.
    """
    values = data or {}
    try:
        return template.async_render(
            variables={**values, "values": values}, parse_result=parse_result
        )
    except TemplateError:
        return None


def resolve_scan_intervals(
    device: DeviceDef, user_min: int = 0
) -> tuple[dict[str, int], int]:
    """Each polling entity's effective poll interval, and the floor applied.

    Cadence resolves per entity: its own ``scan_interval``, else the device's
    ``scan_interval``, else 30 s. The floor is ``max(user_min, device.min_scan_interval
    or the config's lowest cadence)`` — an unset ``min_scan_interval`` imposes no floor
    (it equals the fastest cadence, so nothing is clamped); only ``min_scan_interval``
    or the config-entry option can raise it. Every interval is ``max(floor, cadence)``.
    """
    device_scan = device.scan_interval or DEFAULT_SCAN_INTERVAL
    cadences = {e.key: e.scan_interval or device_scan for e in device.entities if e.polls}
    floor = max(user_min, device.min_scan_interval or min([device_scan, *cadences.values()]))
    return {key: max(floor, cadence) for key, cadence in cadences.items()}, floor


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

        # Buttons never read; read_register entities read via another entity's value
        # (rendered below), not from their own (write) register; static_value entities
        # are write-only command registers. optimistic_default entities do read (with
        # a fallback), so they stay in _readers.
        self._readers = [e for e in device.entities if e.polls]
        self._linked = [e for e in device.entities if e.read_register is not None]
        self._static = [e for e in device.entities if e.static_value is not None]
        self._link_templates: dict[str, Any] = {}
        self.entity_defs = {e.key: e for e in device.entities}
        user_min: int = entry.options.get(OPTION_MIN_SCAN_INTERVAL) or 0
        self._interval_for, floor = resolve_scan_intervals(device, user_min)
        self._tick: int = min(self._interval_for.values(), default=floor)
        self._next_due: dict[str, float] = dict.fromkeys(self._interval_for, 0.0)
        # Device-declared dead registers seed the same set the planner grows from
        # failed reads, so they are never read or bridged across.
        self._holes: set[tuple[str, int]] = set(device.bad_addresses)
        self._cache: dict[tuple[str, int], int | bool] = {}
        self._consecutive_failures = 0
        # Read efficiency (diagnostic): block merging lets one Modbus read cover many
        # entities, so these are typically far below read_entity_count.
        self.last_read_count = 0    # block reads issued in the last refresh
        self.last_polled_count = 0  # entities that refresh actually covered

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

    @property
    def read_entity_count(self) -> int:
        """Total entities that poll — the denominator for ``last_read_count``."""
        return len(self._readers)

    @property
    def full_refresh_read_count(self) -> int:
        """Modbus block reads a complete refresh issues — every reader due at once.

        Block merging keeps this well below :attr:`read_entity_count`. Unlike
        ``last_read_count`` (which dips on cycles where only the fast entities are
        due), it is stable — it shifts only when the read plan does: a config
        reload, or a rejected bridge address teaching the planner a new hole. That
        stability is what keeps the diagnostic sensor cheap for the recorder.
        """
        if not self._readers:
            return 0
        blocks = plan_blocks(
            {e.span for e in self._readers},
            max_read=self.device_def.max_read,
            max_gap=self.device_def.max_gap,
            holes=self._holes,
            boundaries=self.device_def.boundaries,
        )
        return len(blocks)

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
        value = render_over_values(Template(source, self.hass), self.data, parse_result=False)
        if value is None:
            return None
        value = str(value).strip()
        return value if value and "None" not in value else None

    # --- reading -------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        now = time.monotonic()
        due = [e for e in self._readers if self._next_due[e.key] <= now]
        data: dict[str, Any] = dict(self.data) if self.data else {}
        # Seed write-only entities so they are available before the first write.
        for defn in self._static:
            data.setdefault(defn.key, defn.static_value)
        if not due:
            return data

        spans = {e.span for e in due}
        blocks = plan_blocks(
            spans,
            max_read=self.device_def.max_read,
            max_gap=self.device_def.max_gap,
            holes=self._holes,
            boundaries=self.device_def.boundaries,
        )
        ok_blocks = 0
        reads = 0
        async with self.client.lock:
            if not await self.client.ensure_connected():
                self._register_failure()
                raise UpdateFailed(
                    f"cannot connect to gateway {self.client.host}:{self.client.port}"
                )
            for block in blocks:
                yielded, n = await self._read_with_fallback(block, spans)
                ok_blocks += yielded
                reads += n
        self.last_read_count = reads
        self.last_polled_count = len(due)

        if not ok_blocks:
            self._register_failure()
            raise UpdateFailed(f"device {self.slave_id} did not answer any read")
        self._register_success()

        for defn in due:
            value = self._decode(defn)
            if value is None and defn.optimistic_default is not None:
                value = defn.optimistic_default  # keep the control usable
            data[defn.key] = self._postprocess(defn, data.get(defn.key), value)
            self._next_due[defn.key] = now + self._interval_for[defn.key]
        # read_register entities take their value from other (just-decoded) values
        for defn in self._linked:
            data[defn.key] = self._render_link(defn, data)
        return data

    def _render_link(self, defn: EntityDef, data: dict[str, Any]) -> Any:
        """Render a read_register template to this entity's current value."""
        source = defn.read_register
        if source is None:
            return None
        template = self._link_templates.get(defn.key)
        if template is None:
            template = self._link_templates[defn.key] = Template(source, self.hass)
        return render_over_values(template, data)

    async def _read_with_fallback(self, block: Span, spans: set[Span]) -> tuple[int, int]:
        """Read one block; on failure retry its spans without gap bridging.

        Returns ``(yielded, reads)``: ``yielded`` is 1 if anything was read (else
        0), and ``reads`` is how many Modbus read transactions were issued. If the
        block only failed because of bridged filler addresses, remember those as
        holes so future plans avoid them.
        """
        try:
            self._store(block, await self.client.read_block(self.slave_id, block))
            return 1, 1
        except ReadError as err:
            _LOGGER.debug("Block %s failed (%s), retrying unbridged", block, err)

        needed = spans_in_block(block, spans)
        sub_blocks = plan_blocks(needed, max_read=self.device_def.max_read)
        if sub_blocks == [block]:
            self._clear(block)
            _LOGGER.debug("Unbridged read %s failed too", block)
            return 0, 1  # the failed read still hit the wire

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
        return (1 if any_ok else 0), 1 + len(sub_blocks)  # initial try + each sub-read

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

    def _render_write_words(self, defn: EntityDef, items: tuple[Any, ...]) -> list[int]:
        """Render a button's list write_value into consecutive register words.

        Each item is a number or a Jinja template, rendered over the current values
        (so it can use now()/utcnow() or other entity keys). Each must resolve to a
        16-bit integer; negatives are written two's-complement.
        """
        words: list[int] = []
        for item in items:
            rendered = (
                render_over_values(Template(item, self.hass), self.data)
                if isinstance(item, str)
                else item
            )
            if isinstance(rendered, bool) or not isinstance(rendered, (int, float)):
                raise WriteError(
                    f"{defn.key}: write_value item {item!r} rendered to {rendered!r}, "
                    "expected a number"
                )
            num = round(rendered)
            if not -0x8000 <= num <= 0xFFFF:
                raise WriteError(
                    f"{defn.key}: write_value {num} is out of 16-bit register range"
                )
            words.append(num & 0xFFFF)
        return words

    async def _perform_write(self, defn: EntityDef, value: Any) -> Any:
        """Write ``value`` for ``defn``; the client lock is held and connected.

        Returns the value to confirm with — a single-template button resolves its
        template here so the caller can echo the rendered value back.
        """
        if isinstance(value, tuple):
            # button list write_value: render each item to a register word and
            # write them to consecutive registers in one FC16 transaction.
            words = self._render_write_words(defn, value)
            await self.client.write_registers(
                self.slave_id, defn.address, words, multiple=True
            )
            return value
        if defn.platform == "button" and isinstance(value, str):
            # a single Jinja template write_value: render it, then encode through
            # the codec below (honouring the entity's type/map/etc.).
            value = render_over_values(Template(value, self.hass), self.data)
            if value is None:
                raise WriteError(
                    f"{defn.key}: write_value template rendered to nothing"
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
            await self.client.write_registers(
                self.slave_id, defn.address, payload, multiple=defn.write_multiple
            )
        return value

    async def _confirm_write(self, defn: EntityDef, value: Any) -> Any:
        """Read a just-written non-button entity back to confirm it (lock held).

        Entities with no own read-back (read_register / static_value) echo the
        written value instead.
        """
        if defn.read_register is not None or defn.static_value is not None:
            return value  # no read-back; read elsewhere or not at all
        self._store(defn.span, await self.client.read_block(self.slave_id, defn.span))
        confirmed = self._decode(defn)
        if confirmed is None and defn.optimistic_default is not None:
            confirmed = defn.optimistic_default
        return confirmed

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
                value = await self._perform_write(defn, value)
                if defn.platform != "button":
                    confirmed = await self._confirm_write(defn, value)
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
