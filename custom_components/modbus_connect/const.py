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

# Config entry option keys
OPTION_MIN_SCAN_INTERVAL: Final = "min_scan_interval"
# List of enabled group names; absent means "use the device file's default_groups".
OPTION_ENABLED_GROUPS: Final = "enabled_groups"

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
