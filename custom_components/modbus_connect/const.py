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
