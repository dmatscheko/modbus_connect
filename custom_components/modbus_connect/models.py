"""Plain data model for device definitions.

This module is deliberately free of Home Assistant imports so that the codec,
the block planner, and the converter can be used and tested standalone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Modbus tables
TABLE_HOLDING = "holding"
TABLE_INPUT = "input"
TABLE_COIL = "coil"
TABLE_DISCRETE = "discrete"

# The four tables in documentation order — also the section order of a device
# file. The one ordered source; the sets below and all support tooling derive
# from it.
TABLES = (TABLE_HOLDING, TABLE_INPUT, TABLE_COIL, TABLE_DISCRETE)

WORD_TABLES = frozenset({TABLE_HOLDING, TABLE_INPUT})
BIT_TABLES = frozenset({TABLE_COIL, TABLE_DISCRETE})
WRITABLE_TABLES = frozenset({TABLE_HOLDING, TABLE_COIL})
ALL_TABLES = frozenset(TABLES)

# Modbus protocol limits per read request
PROTOCOL_MAX_REGISTERS = 125
PROTOCOL_MAX_BITS = 2000

# Device-level read-planning defaults, defined here (the HA-import-free module)
# so the DeviceDef fields below and const.py agree on one value; const.py
# re-exports them as Final (it can't be imported here — it pulls in Home Assistant).
DEFAULT_MAX_READ = 8
DEFAULT_MAX_GAP = 8

# Value types for word tables ("bool" is implied for bit tables), in bits per
# value. Sub-word values sit in the least significant bits of their register;
# with sum_scale, elements are taken from each register least-significant-first
# ("swap: byte" flips the byte order for devices that pack high byte first).
TYPE_BITS = {
    "bit": 1,
    "uint8": 8,
    "int8": 8,
    "uint16": 16,
    "int16": 16,
    "uint32": 32,
    "int32": 32,
    "uint64": 64,
    "int64": 64,
    "float16": 16,
    "float32": 32,
    "float64": 64,
}
TYPE_ALIASES = {"int1": "bit"}
# Registers occupied by one value of each type
TYPE_WIDTH = {t: max(1, bits // 16) for t, bits in TYPE_BITS.items()}
TYPE_STRING = "string"
# A time-of-day. One register (default): high byte = hour, low byte = minute
# (use ``swap: byte`` for devices that pack minute high / hour low). Two registers
# (``count: 2``): first register = hour, second = minute (SolaX separate-register form).
TYPE_TIME = "time"
TYPE_BOOL = "bool"
FLOAT_TYPES = frozenset({"float16", "float32", "float64"})
SIGNED_TYPES = frozenset({"int8", "int16", "int32", "int64"})
UNSIGNED_INT_TYPES = frozenset(TYPE_BITS) - FLOAT_TYPES - SIGNED_TYPES

# Entity platforms
PLATFORMS = frozenset(
    {
        "sensor",
        "binary_sensor",
        "number",
        "select",
        "switch",
        "text",
        "time",
        "button",
        "valve",
    }
)
WRITING_PLATFORMS = frozenset(
    {"number", "select", "switch", "text", "time", "button", "valve"}
)

# Platforms available in the template: section
TEMPLATE_PLATFORMS = frozenset(
    {
        "sensor",
        "binary_sensor",
        "switch",
        "number",
        "select",
        "light",
        "fan",
        "cover",
        "climate",
    }
)

SWAP_MODES = frozenset({"byte", "word", "word_byte"})


def derive_name(key: str) -> str:
    """Default display label for an identifier: underscores become spaces and
    the first letter is capitalized, the rest keeps its case
    (``parallel_mode`` -> ``Parallel mode``, ``CO2_level`` -> ``CO2 level``).
    Shared by entity/template name defaults and group-switch labels."""
    return (key[:1].upper() + key[1:]).replace("_", " ")


def reverse_value_map(
    value_map: dict[int, str], *, require_unique: bool = False
) -> dict[str, int]:
    """Invert a raw→label ``value_map`` to label→raw.

    With ``require_unique`` (the write path), a non-injective map — two raw
    values sharing a label — raises :class:`ValueError`, because a write can't
    be reversed unambiguously. Without it (the template ``key()`` read helper),
    later labels simply win: a best-effort lookup, never an error.
    """
    reversed_map = {label: raw for raw, label in value_map.items()}
    if require_unique and len(reversed_map) != len(value_map):
        raise ValueError("value_map is not injective")
    return reversed_map


@dataclass(frozen=True, order=True)
class Span:
    """A contiguous range of addresses in one Modbus table."""

    table: str
    start: int
    count: int

    @property
    def end(self) -> int:
        """One past the last address."""
        return self.start + self.count

    def __str__(self) -> str:
        """Compact locator for logs and errors: ``table@start+count``."""
        return f"{self.table}@{self.start}+{self.count}"


@dataclass(frozen=True)
class EntityDef:
    """One entity as defined in a device YAML file."""

    key: str
    platform: str
    table: str = TABLE_HOLDING
    address: int = 0
    type: str = "uint16"
    count: int = 1
    swap: str | None = None
    sum_scale: tuple[float, ...] | None = None
    mask: int | None = None
    multiplier: float | None = None
    offset: float | None = None
    value_map: dict[int, str] | None = None  # YAML key: map
    flags: dict[int, str] | None = None  # bit number (0-indexed) -> name
    # Values meaning on/off for switch/binary_sensor. (Not named plain on/off:
    # unquoted `on:`/`off:` are YAML 1.1 booleans, so those keys need quoting.)
    on_value: int | bool | None = None
    off_value: int | bool | None = None
    # Button press payload: a fixed number/bool, or a tuple of numbers and Jinja
    # template strings written to consecutive registers (FC16) — e.g. an RTC sync.
    write_value: Any = None
    # Some settings echo their value on a different register (or table) than the
    # one they are written to. ``read_register`` is a Jinja template (like the
    # template: section) whose result is the entity's current value; this entity's
    # own address/table/codec are then used only for writing.
    read_register: str | None = None
    # Never read: the entity shows this value until first written, then whatever was
    # last written to it — write-only command registers (e.g. SolaX "direct" control).
    static_value: Any = None
    # Read the register as usual, but fall back to this value when it decodes to
    # nothing (undecodable / out of range), so the control stays usable rather than
    # going unavailable. Mutually exclusive with static_value; both keep the entity
    # always available (their value is never None).
    optimistic_default: Any = None
    # Force FC16 for the write, even for a single register — some devices require
    # it on certain registers (SolaX WRITE_MULTISINGLE).
    write_multiple: bool = False
    # Seconds to wait between a write and its confirming read-back — for devices
    # that apply writes slowly, where an immediate read still returns the old
    # value. The connection lock is held while waiting (the bus stays quiet).
    confirm_delay: float | None = None
    # time entities only: show an out-of-range time (e.g. 24:00) as 23:59 instead
    # of nothing, so the slot stays usable.
    rectify_time: bool = False
    read_modify_write: bool = False
    max_change: float | None = None
    never_resets: bool = False
    # Per-entity poll cadence; overrides the device default, then clamped up by the
    # effective minimum (device.min_scan_interval / the config-entry option).
    scan_interval: int | None = None
    duplicate_as_sensor: bool = False
    # Group tags. The entity is created (and its register polled) only when at
    # least one of these groups is enabled; an entity with no groups is always
    # shown. Groups are independent (OR) — tiers like basic/advanced are expressed
    # by listing every tier an entity belongs to, e.g. ``[basic, advanced, all]``.
    groups: tuple[str, ...] = ()
    # Validated Home Assistant EntityDescription passthrough (aliases resolved)
    ha: dict[str, Any] = field(default_factory=dict)

    @property
    def span(self) -> Span:
        """The address range this entity needs."""
        return Span(self.table, self.address, self.count)

    @property
    def writes(self) -> bool:
        """Whether this entity's platform writes to the device."""
        return self.platform in WRITING_PLATFORMS

    @property
    def internal(self) -> bool:
        """Polled for templates only; no Home Assistant entity is created."""
        return self.platform == "internal"

    @property
    def polls(self) -> bool:
        """Whether the coordinator reads this entity's own register each cycle.

        False for buttons (write-only), ``read_register`` entities (value comes
        from another entity), and ``static_value`` entities (write-only command
        registers). ``optimistic_default`` entities still poll.
        """
        return (
            self.platform != "button"
            and self.read_register is None
            and self.static_value is None
        )


@dataclass(frozen=True)
class WriteTarget:
    """A template action: write a value to one of the device's entities.

    Exactly one flavor per action kind: a fixed ``value`` (turn_on/open/...),
    a ``value_map`` translating the UI value (mode -> written value), or
    neither — then the UI value itself is written (set_temperature/...).
    """

    entity: str  # entity key; must live in a writable table
    value: object | None = None  # fixed payload for on/off-style actions
    value_map: dict[str, object] | None = None  # e.g. hvac mode -> written value


@dataclass(frozen=True)
class SwitchTarget:
    """A template action whose target entity is chosen at write time.

    ``selector`` is a Jinja template; its rendered value picks one of the
    ``cases`` (each a plain :class:`WriteTarget`). This lets a single action
    write to different entities depending on another register — e.g. writing
    the active temperature setpoint chosen by a regulation-type selector.
    """

    selector: str  # Jinja template rendered to a case key at write time
    cases: dict[str, WriteTarget]  # selector value -> target


@dataclass(frozen=True)
class TemplateDef:
    """One entry of the template: section.

    ``config`` holds the validated platform-specific keys: Jinja template
    sources (strings), static numbers/lists, and :class:`WriteTarget` actions.
    """

    key: str
    platform: str  # one of TEMPLATE_PLATFORMS
    ha: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    # Group tags, same meaning as EntityDef.groups.
    groups: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeviceDef:
    """A device YAML file, parsed and validated."""

    manufacturer: str
    model: str
    entities: tuple[EntityDef, ...]
    templates: tuple[TemplateDef, ...] = ()
    max_read: int = DEFAULT_MAX_READ  # max registers/bits per read request
    max_gap: int = DEFAULT_MAX_GAP  # bridge unused holes up to this many addresses
    # (table, address) pairs the planner must never read or bridge across
    # (device-declared dead registers), and addresses that must always start a
    # new read block (a forced boundary between two otherwise-mergeable spans).
    bad_addresses: frozenset[tuple[str, int]] = frozenset()
    boundaries: frozenset[tuple[str, int]] = frozenset()
    # Poll cadence. ``scan_interval`` is the device default that entities without
    # their own inherit; ``min_scan_interval`` is a hard floor the config-entry
    # option can raise further but never lower.
    scan_interval: int | None = None
    min_scan_interval: int | None = None
    # Connection tuning for slow devices and picky RS-485 gateways. ``timeout``
    # (seconds per request) and ``retries`` feed the gateway connection;
    # ``request_delay`` (seconds) enforces silence between any two transactions
    # on it. The connection is shared per gateway: when several entries share
    # one, the largest requested value wins.
    timeout: float | None = None
    retries: int | None = None
    request_delay: float | None = None
    modbus_id: int | None = None  # factory-default Modbus device id
    prefix: str | None = None  # default entity-id prefix
    # Device-info templates, rendered once from the first read (see coordinator).
    sw_version: str | None = None
    hw_version: str | None = None
    serial_number: str | None = None
    # Groups enabled by default when the config entry has no explicit choice yet.
    # Empty means "no default set" — the coordinator then shows every group.
    default_groups: tuple[str, ...] = ()
    # Optional display-name overrides for group switches, as (group, label)
    # pairs. A group without an entry falls back to the derived name.
    group_labels: tuple[tuple[str, str], ...] = ()
    filename: str = ""

    @property
    def group_names(self) -> tuple[str, ...]:
        """All group names used by any entity or template, in first-seen order."""
        seen: dict[str, None] = {}
        for groups in (
            *(e.groups for e in self.entities),
            *(t.groups for t in self.templates),
        ):
            for group in groups:
                seen.setdefault(group, None)
        return tuple(seen)

    def group_label(self, name: str) -> str:
        """Human label for a group's switch: the file's ``group_labels`` override
        if any, else the :func:`derive_name` default (``parallel_mode`` ->
        ``Parallel mode``)."""
        for key, label in self.group_labels:
            if key == name:
                return label
        return derive_name(name)
