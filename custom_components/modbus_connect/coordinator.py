"""Polling coordinator: plans block reads, caches raw registers, decodes values."""

from __future__ import annotations

import asyncio
import logging
import math
import re
import struct
import time
from collections import deque
from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import codec
from .client import ModbusBlockClient, ReadError, WriteError
from .const import (
    BASIC_GROUP,
    CONF_PREFIX,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HEALTH_WINDOW_SECONDS,
    MAX_BACKOFF_SECONDS,
    OPTION_ENABLED_GROUPS,
    OPTION_MIN_SCAN_INTERVAL,
    OPTION_SHOW_ALL,
    QUARANTINE_AFTER,
    QUARANTINE_RETRY_SECONDS,
)
from .models import TABLE_COIL, DeviceDef, EntityDef, Span, SwitchTarget, TemplateDef
from .planner import bridged_addresses, plan_blocks, spans_in_block

_LOGGER = logging.getLogger(__name__)

type ModbusConnectConfigEntry = ConfigEntry[ModbusConnectCoordinator]

# A read_register template that is just one key, e.g. "{{ other_key }}". Rendering
# through Jinja would stringify the source value; plain references instead copy it
# as-is, which keeps non-string values (a time readback's datetime.time) intact.
_DIRECT_LINK = re.compile(r"\s*\{\{\s*([A-Za-z_]\w*)\s*\}\}\s*\Z")


def render_over_values(
    template: Template,
    data: dict[str, Any] | None,
    *,
    parse_result: bool = True,
    key_fn: Callable[[str], Any] | None = None,
) -> Any:
    """Render a compiled template over the device's decoded values.

    Each entity key is injected as a plain variable, plus a ``values`` dict for
    keys that are not valid identifiers. Returns None if the template raises.
    This is the one convention shared by the template: section, ``read_register``,
    and the device-info fields.

    ``key_fn`` is exposed as ``key(name)``: it returns the raw register value
    behind a mapped entity's current option (its ``map:`` key), so a template can
    compare against the stable number instead of the translated label — e.g.
    ``key('operation_status') == 4`` rather than ``operation_status == 'Warmwasser'``.
    """
    values = data or {}
    variables: dict[str, Any] = {**values, "values": values}
    if key_fn is not None:
        variables["key"] = key_fn
    try:
        return template.async_render(variables=variables, parse_result=parse_result)
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


def resolve_enabled_groups(
    device: DeviceDef, options: dict[str, Any] | None
) -> frozenset[str]:
    """Which named entity groups are active for this entry.

    The config-entry option wins when set; otherwise the device file's
    ``default_groups``. The selection is filtered to the file's declared groups,
    so stale names from a previously configured device file drop out. The
    ``basic`` group is special: it is always enabled (and gets no toggle
    switch), so a device's baseline entities cannot be hidden.
    """
    chosen = (options or {}).get(OPTION_ENABLED_GROUPS)
    if chosen is None:
        chosen = device.default_groups
    names = set(device.group_names)
    return frozenset(g for g in chosen if g in names) | {BASIC_GROUP}


def resolve_show_all(device: DeviceDef, options: dict[str, Any] | None) -> bool:
    """Whether group handling is bypassed so every entity shows.

    Permanently on for a device file that uses no groups — there is nothing to
    toggle, so no switch exists either. Otherwise the show-all option wins when
    set (the "Show all entities" switch). With nothing chosen anywhere, a file
    that declares no ``default_groups`` starts with everything visible.
    """
    if not device.group_names:
        return True
    options = options or {}
    flag = options.get(OPTION_SHOW_ALL)
    if flag is not None:
        return bool(flag)
    return OPTION_ENABLED_GROUPS not in options and not device.default_groups


def is_group_visible(groups: tuple[str, ...], enabled: frozenset[str]) -> bool:
    """Whether an item tagged ``groups`` is shown under the ``enabled`` groups.

    Any overlap with the item's own groups suffices. An untagged item is in no
    group at all, so in a grouped device file it only appears through the
    show-all bypass (see resolve_show_all); in a file without groups the bypass
    is permanently on and everything shows.
    """
    return bool(enabled.intersection(groups))


def referenced_read_keys(
    device: DeviceDef,
    visible_entities: list[EntityDef],
    visible_templates: list[TemplateDef],
) -> set[str]:
    """Keys whose registers must stay polled to serve the visible items.

    A shown template or ``read_register`` entity reads other keys through Jinja —
    and those source entities may themselves be hidden (e.g. a basic ``grid_import``
    template reading a hidden ``measured_power`` sensor). Write-time templates read
    too: a button's ``write_value`` and an action's ``by:`` selector render over the
    current values. This returns the transitive closure of all such references,
    seeded from the visible items and from the device-info templates (which always
    render), so nothing a shown value depends on gets pruned from the read plan.
    """
    sources: dict[str, list[str]] = {}
    for e in device.entities:
        if e.read_register is not None:
            sources.setdefault(e.key, []).append(e.read_register)
        if isinstance(e.write_value, str):
            sources.setdefault(e.key, []).append(e.write_value)
        elif isinstance(e.write_value, tuple):
            sources.setdefault(e.key, []).extend(
                item for item in e.write_value if isinstance(item, str)
            )
    for t in device.templates:
        strings = [v for v in t.config.values() if isinstance(v, str)]
        strings += [v.selector for v in t.config.values() if isinstance(v, SwitchTarget)]
        if strings:
            sources.setdefault(t.key, []).extend(strings)

    all_keys = {e.key for e in device.entities} | {t.key for t in device.templates}
    if not all_keys:
        return set()
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(k) for k in sorted(all_keys, key=len, reverse=True)) + r")\b"
    )

    referenced: set[str] = set()
    stack: list[str] = []

    def visit(texts: list[str]) -> None:
        for text in texts:
            for key in pattern.findall(text):
                if key not in referenced:
                    referenced.add(key)
                    stack.append(key)

    for info in (device.sw_version, device.hw_version, device.serial_number):
        if info:
            visit([info])
    for key in (
        *(e.key for e in visible_entities),
        *(t.key for t in visible_templates),
    ):
        visit(sources.get(key, []))
    while stack:
        visit(sources.get(stack.pop(), []))
    return referenced


class ModbusConnectCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """One coordinator per configured device (gateway + Modbus device id).

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
        self.device_id: int = entry.data[CONF_SLAVE_ID]
        self.entry_id = entry.entry_id

        # Group visibility. Only entities/templates in an enabled group are created,
        # and only the registers those (and their data dependencies) need are polled.
        # The show-all bypass ignores the group selection entirely (and is
        # permanently on for files without groups). See resolve_enabled_groups /
        # resolve_show_all / referenced_read_keys.
        self.enabled_groups = resolve_enabled_groups(device, dict(entry.options))
        self.show_all = resolve_show_all(device, dict(entry.options))
        self.all_groups = device.group_names
        # Internal entities never become HA entities; they are read only when a
        # visible item depends on them (via the closure below), so a readback for a
        # now-hidden setting is not polled. Non-internal entities show per their group.
        self.visible_entities = tuple(
            e
            for e in device.entities
            if not e.internal
            and (self.show_all or is_group_visible(e.groups, self.enabled_groups))
        )
        self.visible_templates = tuple(
            t
            for t in device.templates
            if self.show_all or is_group_visible(t.groups, self.enabled_groups)
        )
        needed = {e.key for e in self.visible_entities} | referenced_read_keys(
            device, list(self.visible_entities), list(self.visible_templates)
        )

        # Buttons never read; read_register entities read via another entity's value
        # (rendered below), not from their own (write) register; static_value entities
        # are write-only command registers. optimistic_default entities do read (with
        # a fallback), so they stay in _readers. Each is kept only when a visible item
        # (or a data dependency of one) needs its key.
        self._readers = [e for e in device.entities if e.polls and e.key in needed]
        self._linked = [
            e for e in device.entities if e.read_register is not None and e.key in needed
        ]
        self._static = [
            e for e in device.entities if e.static_value is not None and e.key in needed
        ]
        self._link_templates: dict[str, Any] = {}
        # Per-refresh hooks (see async_add_refresh_callback). Separate from the
        # coordinator listeners, which always_update=False skips on unchanged data.
        self._refresh_callbacks: list[Callable[[dict[str, Any]], None]] = []
        self.entity_defs = {e.key: e for e in device.entities}
        # value label -> raw map key, per mapped entity, for the template key()
        # helper. Built once (maps never change at runtime); a translated map
        # reverses just the same, so key() stays language-independent.
        self._value_reverse: dict[str, dict[Any, int]] = {
            e.key: {label: raw for raw, label in e.value_map.items()}
            for e in device.entities
            if e.value_map is not None
        }
        user_min: int = entry.options.get(OPTION_MIN_SCAN_INTERVAL) or 0
        interval_for, floor = resolve_scan_intervals(device, user_min)
        self._interval_for = {e.key: interval_for[e.key] for e in self._readers}
        self._tick: int = min(self._interval_for.values(), default=floor)
        self._next_due: dict[str, float] = dict.fromkeys(self._interval_for, 0.0)
        # Device-declared dead registers seed the same set the planner grows from
        # failed reads, so they are never read or bridged across.
        self.holes: set[tuple[str, int]] = set(device.bad_addresses)
        self._cache: dict[tuple[str, int], int | bool] = {}
        # Keys whose last read failed and that already got their one quick retry;
        # see _async_update_data.
        self._retried: set[str] = set()
        self._full_plan_cache: tuple[int, int] | None = None
        self.consecutive_failures = 0
        # Read efficiency (diagnostic): block merging lets one Modbus read cover many
        # entities, so these are typically far below read_entity_count.
        self.last_read_count = 0    # block reads issued in the last refresh
        self.last_polled_count = 0  # entities that refresh actually covered
        # Read health (diagnostic): unrecovered polling failures — failed read
        # transactions and failed connection attempts. The deque feeds the
        # "failed in the last 5 minutes" indicator, the total its counter, and
        # the per-key counts (in diagnostics) point at the entity whose register
        # the device refuses to serve.
        self.failed_read_total = 0
        self._failure_times: deque[float] = deque()
        self.failed_reads_by_key: dict[str, int] = {}
        # Registers the device keeps refusing (while answering everything else)
        # are quarantined out of the read plan and re-probed on a slow cadence:
        # entity key → monotonic time of the next probe. Runtime state — a
        # reload clears it, like the learned holes above.
        self.quarantined: dict[str, float] = {}
        self._fail_streak: dict[str, int] = {}
        self._cycle_illegal: set[str] = set()

        # The prefix drives entity ids; the name is the device/entry title.
        # Old entries stored their device name in CONF_PREFIX.
        self.entity_id_prefix: str = entry.data.get(CONF_PREFIX) or ""
        name = (
            entry.data.get(CONF_NAME)
            or self.entity_id_prefix
            or f"{device.manufacturer} {device.model}"
        )
        # HA's device-info card has no free-form rows, so fold the connection
        # (gateway or serial port, and Modbus id) into model_id — it renders
        # right after the model as "<model> (<target · ID N>)".
        target = (
            entry.data[CONF_SERIAL_PORT]
            if CONF_SERIAL_PORT in entry.data
            else f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
        )
        connection = f"{target} · ID {self.device_id}"
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=name,
            manufacturer=device.manufacturer,
            model=device.model,
            model_id=connection,
        )
        # Meta entities (group toggles, read diagnostics) live on their own
        # service device so the real device shows only the device's entities.
        self.meta_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_meta")},
            name=f"{name} Configuration",
            manufacturer=device.manufacturer,
            entry_type=DeviceEntryType.SERVICE,
            via_device=(DOMAIN, entry.entry_id),
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {self.device_info['name']}",
            update_interval=timedelta(seconds=self._tick),
            # Skip listener/state updates on cycles where no value changed.
            always_update=False,
        )

    @property
    def read_entity_count(self) -> int:
        """Total entities that poll — the denominator for ``last_read_count``."""
        return len(self._readers)

    def _record_read_failure(
        self, span: Span | None = None, *, illegal: bool = False, probe: bool = False
    ) -> None:
        """Count one unrecovered failed read.

        With a ``span``, the failure covered entity registers (not just bridged
        filler), so it is also attributed to the entities in that range — the
        pointer needed to find a register the device genuinely does not serve.
        ``illegal`` (the device explicitly refused the address) fast-tracks
        those entities into quarantine. ``probe`` failures — scheduled re-probes
        of already quarantined registers — stay out of the 5-minute health
        window, so a known-bad register does not keep the problem indicator lit.
        """
        self.failed_read_total += 1
        # Trim on write, not only on read: the window must stay bounded even
        # when nothing polls the health indicator (its entity can be disabled).
        cutoff = time.monotonic() - HEALTH_WINDOW_SECONDS
        while self._failure_times and self._failure_times[0] < cutoff:
            self._failure_times.popleft()
        if not probe:
            self._failure_times.append(time.monotonic())
        if span is None:
            return
        keys = sorted(
            e.key
            for e in self._readers
            if e.table == span.table
            and e.address < span.end
            and e.address + e.count > span.start
        )
        for key in keys:
            self.failed_reads_by_key[key] = self.failed_reads_by_key.get(key, 0) + 1
        if illegal:
            self._cycle_illegal.update(keys)
        if keys:
            _LOGGER.debug(
                "Unrecovered read failure %s %d..%d; affected entities: %s",
                span.table,
                span.start,
                span.end - 1,
                ", ".join(keys),
            )

    def _track_failure_streak(self, defn: EntityDef, now: float) -> None:
        """Count an entity's consecutive unread cycles; quarantine when hopeless.

        Only reached on partial failures — a cycle where nothing answers raises
        before decoding, so an unreachable device or gateway never quarantines
        anything. An explicit illegal-address answer skips the streak: the
        device itself said the register does not exist.
        """
        key = defn.key
        streak = self._fail_streak[key] = self._fail_streak.get(key, 0) + 1
        if streak < QUARANTINE_AFTER and key not in self._cycle_illegal:
            return
        reason = (
            "is an illegal address for the device"
            if key in self._cycle_illegal
            else f"failed {streak} consecutive polls"
        )
        self._fail_streak.pop(key, None)
        self.quarantined[key] = now + QUARANTINE_RETRY_SECONDS
        _LOGGER.warning(
            "%s: %s (%s@%d+%d) %s while the device answers other reads; pausing "
            "it and re-probing every %d s. If it never recovers, fix or remove "
            "the entity in the device file",
            self.name,
            key,
            defn.table,
            defn.address,
            defn.count,
            reason,
            QUARANTINE_RETRY_SECONDS,
        )

    @property
    def read_failures_in_window(self) -> int:
        """Unrecovered read failures within the last HEALTH_WINDOW_SECONDS."""
        cutoff = time.monotonic() - HEALTH_WINDOW_SECONDS
        while self._failure_times and self._failure_times[0] < cutoff:
            self._failure_times.popleft()
        return len(self._failure_times)

    @property
    def quarantine_status(self) -> dict[str, int]:
        """Quarantined entity keys → seconds until their next re-probe."""
        now = time.monotonic()
        return {k: max(0, round(t - now)) for k, t in sorted(self.quarantined.items())}

    def monotonic_time(self) -> float:
        """The clock integrating template sensors measure refresh intervals with
        (here so tests drive it together with the scan-interval clock)."""
        return time.monotonic()

    def entities_for(self, platform: str) -> Iterator[EntityDef]:
        """Visible register-backed entities of one platform (the per-platform
        ``async_setup_entry`` filter, in one place)."""
        return (e for e in self.visible_entities if e.platform == platform)

    def templates_for(self, platform: str) -> Iterator[TemplateDef]:
        """Visible template entities of one platform."""
        return (t for t in self.visible_templates if t.platform == platform)

    @property
    def group_switch_names(self) -> tuple[str, ...]:
        """The named groups that get a toggle switch (the always-on ``basic``
        gets none). The show-all switch is separate — it exists whenever the
        device file uses groups at all."""
        return tuple(g for g in self.all_groups if g != BASIC_GROUP)

    @property
    def provided_unique_ids(self) -> set[str]:
        """Unique ids of every entity the current configuration provides.

        The registry-cleanup button keeps exactly these; any other registry
        entry of this config entry is a leftover — a group-hidden entity or a
        stale key from an earlier device file — and may be removed. Must cover
        every unique id any platform module creates.
        """
        ids = {f"{self.entry_id}_{e.key}" for e in self.visible_entities}
        ids.update(
            f"{self.entry_id}_{e.key}_sensor"
            for e in self.visible_entities
            if e.duplicate_as_sensor and e.platform != "sensor"
        )
        ids.update(f"{self.entry_id}_{t.key}" for t in self.visible_templates)
        ids.update(
            f"{self.entry_id}_group_{group}" for group in self.group_switch_names
        )
        if self.all_groups:
            ids.add(f"{self.entry_id}_show_all_entities")
        ids.add(f"{self.entry_id}_reads_per_refresh")
        ids.add(f"{self.entry_id}_remove_hidden_entities")
        ids.add(f"{self.entry_id}_read_failures")
        ids.add(f"{self.entry_id}_failed_reads")
        return ids

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
        # The plan only shifts when a hole is learned; cache on the hole count so
        # the sensor's state reads don't re-plan every cycle.
        if self._full_plan_cache is None or self._full_plan_cache[0] != len(self.holes):
            blocks = plan_blocks(
                {e.span for e in self._readers},
                max_read=self.device_def.max_read,
                max_gap=self.device_def.max_gap,
                holes=self.holes,
                boundaries=self.device_def.boundaries,
            )
            self._full_plan_cache = (len(self.holes), len(blocks))
        return self._full_plan_cache[1]

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
        value = render_over_values(
            Template(source, self.hass),
            self.data,
            parse_result=False,
            key_fn=self.key_lookup(self.data),
        )
        if value is None:
            return None
        value = str(value).strip()
        return value if value and "None" not in value else None

    # --- reading -------------------------------------------------------------

    def _seeded_data(self) -> dict[str, Any]:
        """A mutable copy of the current data, with write-only statics seeded
        so they are available before the first write."""
        data: dict[str, Any] = dict(self.data) if self.data else {}
        for defn in self._static:
            data.setdefault(defn.key, defn.static_value)
        return data

    def async_add_refresh_callback(
        self, refresh_callback: Callable[[dict[str, Any]], None]
    ) -> Callable[[], None]:
        """Register a hook called with the fresh data after every successful
        refresh — including one where no value changed, which (because of
        ``always_update=False``) never reaches the coordinator listeners. The
        integrating sensors sample time from it: a constant 50 W accumulates
        energy all the same. Returns the unsubscriber."""
        self._refresh_callbacks.append(refresh_callback)

        def _unsubscribe() -> None:
            self._refresh_callbacks.remove(refresh_callback)

        return _unsubscribe

    def _notify_refresh(self, data: dict[str, Any]) -> None:
        for refresh_callback in list(self._refresh_callbacks):
            refresh_callback(data)

    async def _async_update_data(self) -> dict[str, Any]:
        now = time.monotonic()
        self._cycle_illegal.clear()
        due = [
            e
            for e in self._readers
            if e.key not in self.quarantined and self._next_due[e.key] <= now
        ]
        probes = sorted(k for k, t in self.quarantined.items() if t <= now)
        if not due and not probes:
            data = self._seeded_data()
            self._notify_refresh(data)
            return data

        spans = {e.span for e in due}
        blocks = plan_blocks(
            spans,
            max_read=self.device_def.max_read,
            max_gap=self.device_def.max_gap,
            holes=self.holes,
            boundaries=self.device_def.boundaries,
        )
        async with self.client.lock:
            if not await self.client.ensure_connected():
                self._record_read_failure()
                self._register_failure()
                raise UpdateFailed(f"cannot connect to {self.client.target}")
        ok_blocks = 0
        reads = 0
        # The lock is taken per block, not around the whole refresh, so a user
        # write never waits behind a long (or timing-out) poll cycle.
        for block in blocks:
            async with self.client.lock:
                yielded, n = await self._read_with_fallback(block, spans)
            ok_blocks += yielded
            reads += n
        # Quarantined registers re-probe standalone on their own slow cadence,
        # never inside the healthy blocks; a recovered entity rejoins ``due``
        # and decodes below like any other.
        for key in probes:
            if await self._probe_quarantined(key, now):
                ok_blocks += 1
                due.append(self.entity_defs[key])
            reads += 1
        self.last_read_count = reads
        self.last_polled_count = len(due)

        # Failing probes alone are no outage: with no regular block due, the
        # cycle leaves the device's health untouched.
        if blocks and not ok_blocks:
            self._register_failure()
            raise UpdateFailed(f"device {self.device_id} did not answer any read")
        if ok_blocks:
            self._register_success()

        # Copied only now: a write can interleave between the block reads above
        # and push its confirmed value into self.data — a copy taken at refresh
        # start would revert that value for every entity not due this cycle.
        data = self._seeded_data()
        for defn in due:
            value = self._decode(defn)
            unread = value is None and self.missing(defn)
            if unread:
                self._track_failure_streak(defn, now)  # may quarantine the key
            else:
                self._fail_streak.pop(defn.key, None)
            if value is None and defn.optimistic_default is not None:
                value = defn.optimistic_default  # keep the control usable
            data[defn.key] = self._postprocess(defn, data.get(defn.key), value)
            # An entity whose block read failed gets one quick retry on the next
            # tick instead of waiting out its whole interval (which can be long);
            # if the retry fails too, it falls back to the normal cadence. A
            # just-quarantined key gets neither: the slow probe owns it now.
            if defn.key in self.quarantined:
                self._retried.discard(defn.key)
            elif unread and defn.key not in self._retried:
                self._retried.add(defn.key)
            else:
                self._retried.discard(defn.key)
                self._next_due[defn.key] = now + self._interval_for[defn.key]
        # read_register entities take their value from other (just-decoded) values
        for defn in self._linked:
            data[defn.key] = self._render_link(defn, data)
        self._notify_refresh(data)
        return data

    def missing(self, defn: EntityDef) -> bool:
        """Whether any of the entity's addresses is absent from the raw cache
        (i.e. its last block read failed, as opposed to a decode error).

        Public: entity availability uses this to tell a real outage apart
        from an answered read whose value merely fails to decode or map."""
        return any(
            (defn.table, a) not in self._cache
            for a in range(defn.address, defn.address + defn.count)
        )

    def key_lookup(self, data: dict[str, Any] | None) -> Callable[[str], Any]:
        """Build the template ``key(name)`` helper bound to ``data``.

        ``key('mode')`` returns the raw register value behind a mapped entity's
        current option (its ``map:`` key) — a stable number that does not move
        when the option label is translated. A non-mapped (or unknown) entity
        yields its plain value, so ``key(x)`` is always safe to write.
        """
        reverse = self._value_reverse
        values = data or {}

        def key(name: str) -> Any:
            entry = reverse.get(name)
            value = values.get(name)
            return entry.get(value) if entry is not None else value

        return key

    def _render_link(self, defn: EntityDef, data: dict[str, Any]) -> Any:
        """Render a read_register template to this entity's current value."""
        source = defn.read_register
        if source is None:
            return None
        direct = _DIRECT_LINK.match(source)
        if direct is not None:
            return data.get(direct.group(1))
        template = self._link_templates.get(defn.key)
        if template is None:
            template = self._link_templates[defn.key] = Template(source, self.hass)
        return render_over_values(template, data, key_fn=self.key_lookup(data))

    async def _read_with_fallback(self, block: Span, spans: set[Span]) -> tuple[int, int]:
        """Read one block; on failure retry its spans without gap bridging.

        Returns ``(yielded, reads)``: ``yielded`` is 1 if anything was read (else
        0), and ``reads`` is how many Modbus read transactions were issued. If the
        block only failed because of bridged filler addresses, remember those as
        holes so future plans avoid them. A failing retry that still covers
        several spans is isolated once more into one read per span, so a single
        dead register cannot take its readable neighbours down with it.
        """
        try:
            self._store(block, await self.client.read_block(self.device_id, block))
            return 1, 1
        except ReadError as err:
            # Drop the whole failed range before retrying: successful sub-reads
            # re-store their part, and whatever stays failed must not decode from
            # a previous cycle's words (a mixed-generation value).
            self._clear(block)
            block_illegal = err.illegal_address
            _LOGGER.debug("Block %s failed (%s), retrying unbridged", block, err)

        needed = spans_in_block(block, spans)
        sub_blocks = plan_blocks(needed, max_read=self.device_def.max_read)
        # No unbridged sub-plan to fall back to: the block was a single span, a
        # run of adjacent spans that merge straight back into it, or a
        # max_read-sized chunk of a larger span (no span fully inside it).
        if not sub_blocks or sub_blocks == [block]:
            if len(needed) > 1:
                any_ok, n = await self._read_spans_isolated(needed)
                return (1 if any_ok else 0), 1 + n
            self._record_read_failure(block, illegal=block_illegal)
            _LOGGER.debug("No fallback for failed block %s", block)
            return 0, 1  # the failed read still hit the wire

        all_ok = True
        any_ok = False
        reads = 1 + len(sub_blocks)  # initial try + each sub-read
        for sub in sub_blocks:
            try:
                self._store(sub, await self.client.read_block(self.device_id, sub))
                any_ok = True
            except ReadError as err:
                all_ok = False
                _LOGGER.debug("Fallback read %s failed: %s", sub, err)
                inner = spans_in_block(sub, needed)
                if len(inner) > 1:
                    sub_ok, n = await self._read_spans_isolated(inner)
                    any_ok = any_ok or sub_ok
                    reads += n
                else:
                    self._record_read_failure(sub, illegal=err.illegal_address)

        if any_ok and all_ok:
            # Every real span read fine on retry: the initial failure was only
            # bridged filler (learned as holes below, so it will not repeat) —
            # a planning artifact, not a device problem, so it is not recorded.
            new_holes = bridged_addresses(block, needed)
            if new_holes:
                self.holes |= new_holes
                _LOGGER.info(
                    "%s: device rejects %d bridged filler address(es) in the %s table; "
                    "not bridging them again",
                    self.name,
                    len(new_holes),
                    block.table,
                )
        return (1 if any_ok else 0), reads

    async def _read_spans_isolated(self, needed: list[Span]) -> tuple[bool, int]:
        """Read each span on its own to tell a dead register from its neighbours.

        The last resort for a failed unbridged read covering several spans:
        adjacent spans always plan into one block, so only reading them one by
        one can pinpoint which register the device actually refuses.
        """
        any_ok = False
        for span in needed:
            try:
                self._store(span, await self.client.read_block(self.device_id, span))
                any_ok = True
            except ReadError as err:
                self._record_read_failure(span, illegal=err.illegal_address)
                _LOGGER.debug("Isolated read %s failed: %s", span, err)
        return any_ok, len(needed)

    async def _probe_quarantined(self, key: str, now: float) -> bool:
        """One standalone re-probe of a quarantined register; True on recovery.

        Kept out of the regular plan so the known-bad span never drags a healthy
        block down. Success lifts the quarantine; failure schedules the next
        probe and stays out of the health window (see _record_read_failure).
        """
        span = self.entity_defs[key].span
        async with self.client.lock:
            try:
                self._store(span, await self.client.read_block(self.device_id, span))
            except ReadError as err:
                self.quarantined[key] = now + QUARANTINE_RETRY_SECONDS
                self._record_read_failure(span, probe=True)
                _LOGGER.debug("Re-probe of quarantined %s failed: %s", key, err)
                return False
        del self.quarantined[key]
        _LOGGER.info("%s: %s reads again; lifting its quarantine", self.name, key)
        return True

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
        self.consecutive_failures += 1
        delay = min(self._tick * 2**self.consecutive_failures, MAX_BACKOFF_SECONDS)
        self.update_interval = timedelta(seconds=max(self._tick, delay))

    def _register_success(self) -> None:
        if self.consecutive_failures:
            self.consecutive_failures = 0
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
                render_over_values(
                    Template(item, self.hass),
                    self.data,
                    key_fn=self.key_lookup(self.data),
                )
                if isinstance(item, str)
                else item
            )
            if (
                isinstance(rendered, bool)
                or not isinstance(rendered, (int, float))
                or not math.isfinite(rendered)
            ):
                raise WriteError(
                    f"{defn.key}: write_value item {item!r} rendered to {rendered!r}, "
                    "expected a finite number"
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
                self.device_id, defn.address, words, multiple=True
            )
            return value
        if defn.platform == "button" and isinstance(value, str):
            # a single Jinja template write_value: render it, then encode through
            # the codec below (honouring the entity's type/map/etc.).
            value = render_over_values(
                Template(value, self.hass), self.data, key_fn=self.key_lookup(self.data)
            )
            if value is None:
                raise WriteError(
                    f"{defn.key}: write_value template rendered to nothing"
                )
        current_raw: int | None = None
        if defn.mask is not None and defn.read_modify_write:
            raw = await self.client.read_block(self.device_id, defn.span)
            current_raw = int(raw[0])
        payload = codec.encode(defn, value, current_raw=current_raw)
        if defn.table == TABLE_COIL:
            await self.client.write_coil(self.device_id, defn.address, bool(payload))
        else:
            assert isinstance(payload, list)
            await self.client.write_registers(
                self.device_id, defn.address, payload, multiple=defn.write_multiple
            )
        return value

    async def _confirm_write(self, defn: EntityDef, value: Any) -> Any:
        """Read a just-written non-button entity back to confirm it (lock held).

        Entities with no own read-back (read_register / static_value) echo the
        written value instead.
        """
        if defn.read_register is not None or defn.static_value is not None:
            return value  # no read-back; read elsewhere or not at all
        if defn.confirm_delay is not None:
            # The device is still applying the write; holding the lock keeps
            # the bus quiet until the read-back.
            await asyncio.sleep(defn.confirm_delay)
        self._store(defn.span, await self.client.read_block(self.device_id, defn.span))
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
                        f"Cannot connect to {self.client.target}",
                        translation_domain=DOMAIN,
                        translation_key="cannot_connect",
                        translation_placeholders={"target": self.client.target},
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
