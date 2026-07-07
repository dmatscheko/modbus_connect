"""Plain data model for device definitions.

This module is deliberately free of Home Assistant imports so that the codec,
the block planner, and the converter can be used and tested standalone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Modbus tables
TABLE_HOLDING = "holding"
TABLE_INPUT = "input"
TABLE_COIL = "coil"
TABLE_DISCRETE = "discrete"

WORD_TABLES = frozenset({TABLE_HOLDING, TABLE_INPUT})
BIT_TABLES = frozenset({TABLE_COIL, TABLE_DISCRETE})
WRITABLE_TABLES = frozenset({TABLE_HOLDING, TABLE_COIL})
ALL_TABLES = WORD_TABLES | BIT_TABLES

# Modbus protocol limits per read request
PROTOCOL_MAX_REGISTERS = 125
PROTOCOL_MAX_BITS = 2000

# Value types for word tables ("bool" is implied for bit tables)
TYPE_WIDTH = {
    "uint16": 1,
    "int16": 1,
    "uint32": 2,
    "int32": 2,
    "uint64": 4,
    "int64": 4,
    "float32": 2,
    "float64": 4,
}
TYPE_STRING = "string"
TYPE_BOOL = "bool"
FLOAT_TYPES = frozenset({"float32", "float64"})
SIGNED_TYPES = frozenset({"int16", "int32", "int64"})

# Entity platforms
PLATFORMS = frozenset(
    {"sensor", "binary_sensor", "number", "select", "switch", "text", "button"}
)
WRITING_PLATFORMS = frozenset({"number", "select", "switch", "text", "button"})

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
    on_value: int | bool | None = None  # YAML key: on
    off_value: int | bool | None = None  # YAML key: off
    write_value: float | bool | None = None  # button press payload
    read_modify_write: bool = False
    max_change: float | None = None
    never_resets: bool = False
    scan_interval: int | None = None
    duplicate_as_sensor: bool = False
    # Validated Home Assistant EntityDescription passthrough (aliases resolved)
    ha: dict = field(default_factory=dict)

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
class TemplateDef:
    """One entry of the template: section.

    ``config`` holds the validated platform-specific keys: Jinja template
    sources (strings), static numbers/lists, and :class:`WriteTarget` actions.
    """

    key: str
    platform: str  # one of TEMPLATE_PLATFORMS
    ha: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DeviceDef:
    """A device YAML file, parsed and validated."""

    manufacturer: str
    model: str
    entities: tuple[EntityDef, ...]
    templates: tuple[TemplateDef, ...] = ()
    max_read: int = 8  # max registers/bits per read request
    max_gap: int = 8  # bridge unused holes up to this many addresses
    scan_interval: int | None = None  # device default poll interval
    filename: str = ""
