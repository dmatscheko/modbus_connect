"""Constants for the Modbus Connect integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "modbus_connect"

PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.TIME,
]

# Config entry data keys
CONF_SLAVE_ID: Final = "slave_id"
CONF_FILENAME: Final = "filename"
CONF_PREFIX: Final = "prefix"
CONF_FRAMER: Final = "framer"

# Wire framing of the TCP connection (values follow pymodbus FramerType):
# regular Modbus TCP, or raw RTU frames for transparent RS-485 bridges
# (Elfin/USR boxes in transparent mode, ser2net, ...). Entries without the
# key predate the option and mean Modbus TCP.
FRAMER_SOCKET: Final = "socket"
FRAMER_RTU: Final = "rtu"
FRAMER_OPTIONS: Final = [FRAMER_SOCKET, FRAMER_RTU]

# Config entry option keys
OPTION_MIN_SCAN_INTERVAL: Final = "min_scan_interval"
# List of enabled group names; absent means "use the device file's default_groups".
OPTION_ENABLED_GROUPS: Final = "enabled_groups"
# Bypass group handling entirely while true: every non-internal entity is shown,
# whatever the group selection says (the "Show all entities" switch).
OPTION_SHOW_ALL: Final = "show_all_entities"

# The one reserved group name: always enabled, no toggle switch. Tagging an
# entity ``groups: [basic]`` keeps it out of other groups without ever hiding it.
BASIC_GROUP: Final = "basic"

DEFAULT_PORT: Final = 502
DEFAULT_SLAVE_ID: Final = 1
DEFAULT_SCAN_INTERVAL: Final = 30

# Device-level YAML defaults
DEFAULT_MAX_READ: Final = 8
DEFAULT_MAX_GAP: Final = 8

# Directory (relative to the HA config dir) where users can drop their own
# device YAML files; they override built-in files with the same name.
USER_CONFIG_DIR: Final = DOMAIN

# Backoff cap for repeatedly failing devices (seconds)
MAX_BACKOFF_SECONDS: Final = 300

# How far back the read-failures health indicator looks (seconds)
HEALTH_WINDOW_SECONDS: Final = 300

# Quarantine for a register the device keeps refusing while it answers other
# reads (usually a wrong address in the device file): after this many
# consecutive unread polls — or one explicit illegal-address answer — the
# entity's registers leave the read plan ...
QUARANTINE_AFTER: Final = 3
# ... and are re-probed standalone this often (seconds); success lifts the
# quarantine, as does reloading the entry.
QUARANTINE_RETRY_SECONDS: Final = 600
