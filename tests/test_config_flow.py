"""Config, reconfigure, and options flow tests."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import voluptuous as vol
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.modbus_connect.config_flow import _probe_span, _unique_id
from custom_components.modbus_connect.const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_FILENAME,
    CONF_FRAMER,
    CONF_PARITY,
    CONF_PREFIX,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    DOMAIN,
    FRAMER_RTU,
    FRAMER_SOCKET,
    OPTION_ENABLED_GROUPS,
    OPTION_MIN_SCAN_INTERVAL,
)

DEVICE_YAML = """
device:
  manufacturer: Acme
  model: X1
holding:
  temperature:
    address: 0
    ha:
      platform: sensor
      name: Temperature
"""

DEVICE_YAML_DEFAULTS = """
device:
  manufacturer: Acme
  model: X2
  modbus_id: 42
  prefix: acme_pre
  scan_interval: 15
holding:
  temperature:
    address: 0
    ha:
      platform: sensor
      name: Temperature
"""

DEVICE_STEP = {CONF_FILENAME: "acme_x1.yaml", CONF_NAME: ""}
CONNECTION = {
    "host": "192.0.2.1",
    "port": 502,
    CONF_FRAMER: FRAMER_SOCKET,
    CONF_SLAVE_ID: 7,
    CONF_PREFIX: "",
}
UNIQUE_ID = "192.0.2.1:502:7"


def write_device_file(
    hass: HomeAssistant, name: str = "acme_x1.yaml", content: str = DEVICE_YAML
) -> None:
    """Drop a minimal device file into the user config dir."""
    directory = Path(hass.config.config_dir) / DOMAIN
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(content, encoding="utf-8")


def patch_probe(result: bool):
    """Bypass the wire probe: the device answered, or the gateway is down."""
    return patch(
        "custom_components.modbus_connect.config_flow.async_probe_device",
        return_value=None if result else "cannot_connect",
    )


def patch_setup():
    return patch.multiple(
        "custom_components.modbus_connect",
        async_setup_entry=AsyncMock(return_value=True),
        async_unload_entry=AsyncMock(return_value=True),
    )


def form_defaults(result) -> dict:
    """The prefilled defaults of the shown form, by field name."""
    out = {}
    for key in result["data_schema"].schema:
        default = getattr(key, "default", vol.UNDEFINED)
        out[str(key.schema)] = None if default is vol.UNDEFINED else default()
    return out


async def pick(hass: HomeAssistant, result, step: str):
    """Choose a transport from the connection-type menu."""
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )


async def test_full_flow(hass: HomeAssistant) -> None:
    write_device_file(hass)
    with patch_probe(True), patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], DEVICE_STEP
        )
        result = await pick(hass, result, "connection")
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "connection"
        # No device defaults in the file: modbus id 1, prefix from the title
        assert form_defaults(result)[CONF_SLAVE_ID] == 1
        assert form_defaults(result)[CONF_PREFIX] == "Acme X1"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONNECTION
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Acme X1"
    assert result["data"] == {**DEVICE_STEP, **CONNECTION}
    assert result["result"].unique_id == UNIQUE_ID


async def test_name_becomes_title_and_prefix_default(hass: HomeAssistant) -> None:
    write_device_file(hass)
    with patch_probe(True), patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**DEVICE_STEP, CONF_NAME: "Heat pump"}
        )
        result = await pick(hass, result, "connection")
        assert form_defaults(result)[CONF_PREFIX] == "Heat pump"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**CONNECTION, CONF_PREFIX: "hp"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Heat pump"
    assert result["data"][CONF_NAME] == "Heat pump"
    assert result["data"][CONF_PREFIX] == "hp"


async def test_device_file_defaults_prefill(hass: HomeAssistant) -> None:
    write_device_file(hass, "acme_x2.yaml", DEVICE_YAML_DEFAULTS)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FILENAME: "acme_x2.yaml", CONF_NAME: ""}
    )
    result = await pick(hass, result, "connection")
    defaults = form_defaults(result)
    assert defaults[CONF_SLAVE_ID] == 42
    assert defaults[CONF_PREFIX] == "acme_pre"


async def test_cannot_connect_then_recover(hass: HomeAssistant) -> None:
    write_device_file(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DEVICE_STEP
    )
    result = await pick(hass, result, "connection")
    with patch_probe(False):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONNECTION
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"
    assert result["errors"] == {"base": "cannot_connect"}
    # Entered values survive the retry form
    assert form_defaults(result)["host"] == "192.0.2.1"

    with patch_probe(True), patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONNECTION
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_aborts(hass: HomeAssistant) -> None:
    write_device_file(hass)
    MockConfigEntry(domain=DOMAIN, unique_id=UNIQUE_ID).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DEVICE_STEP
    )
    result = await pick(hass, result, "connection")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONNECTION
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_no_device_files_aborts(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.modbus_connect.config_flow.async_load_all",
        AsyncMock(return_value=({}, {})),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_device_files"


async def test_invalid_device_file_reported_in_flow(hass: HomeAssistant) -> None:
    # an invalid user file must not vanish silently from the picker
    write_device_file(hass)
    write_device_file(hass, "broken.yaml", "device: {manufacturer: X}\n")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    note = result["description_placeholders"]["failed"]
    assert "broken.yaml" in note
    assert "device.model" in note  # the actual reason, not just the name


async def test_all_files_valid_shows_no_note(hass: HomeAssistant) -> None:
    # the harness config dir is shared across tests: drop leftover files first
    directory = Path(hass.config.config_dir) / DOMAIN
    if directory.is_dir():
        for stale in directory.glob("*.yaml"):
            stale.unlink()
    write_device_file(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["description_placeholders"] == {"failed": ""}


def make_entry(**overrides) -> MockConfigEntry:
    data = {**CONNECTION, CONF_FILENAME: "acme_x1.yaml", **overrides}
    return MockConfigEntry(
        domain=DOMAIN,
        data=data,
        unique_id=f"{data['host']}:{data['port']}:{data[CONF_SLAVE_ID]}",
        title="Acme X1",
    )


async def start_reconfigure(hass: HomeAssistant, entry: MockConfigEntry):
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    write_device_file(hass)
    write_device_file(hass, "other.yaml")
    entry = make_entry()
    entry.add_to_hass(hass)

    result = await start_reconfigure(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert form_defaults(result)[CONF_FILENAME] == "acme_x1.yaml"

    new_connection = {**CONNECTION, "host": "192.0.2.2"}
    with patch_probe(True), patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_FILENAME: "other.yaml", CONF_NAME: "Renamed"}
        )
        result = await pick(hass, result, "reconfigure_connection")
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure_connection"
        assert form_defaults(result)["host"] == "192.0.2.1"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_connection
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        **new_connection,
        CONF_FILENAME: "other.yaml",
        CONF_NAME: "Renamed",
    }
    assert entry.unique_id == "192.0.2.2:502:7"
    assert entry.title == "Renamed"


async def test_reconfigure_prefills_name_from_old_prefix(hass: HomeAssistant) -> None:
    """Entries created before CONF_NAME stored the device name in the prefix."""
    write_device_file(hass)
    entry = make_entry(**{CONF_PREFIX: "Old name"})
    entry.add_to_hass(hass)

    result = await start_reconfigure(hass, entry)
    assert form_defaults(result)[CONF_NAME] == "Old name"


async def test_reconfigure_same_connection_ok(hass: HomeAssistant) -> None:
    write_device_file(hass)
    entry = make_entry()
    entry.add_to_hass(hass)

    result = await start_reconfigure(hass, entry)
    with patch_probe(True), patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], DEVICE_STEP
        )
        result = await pick(hass, result, "reconfigure_connection")
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure_connection"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONNECTION
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == UNIQUE_ID


async def test_reconfigure_collision_aborts(hass: HomeAssistant) -> None:
    write_device_file(hass)
    other = make_entry(host="192.0.2.9")
    other.add_to_hass(hass)
    entry = make_entry()
    entry.add_to_hass(hass)

    result = await start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DEVICE_STEP
    )
    result = await pick(hass, result, "reconfigure_connection")
    with patch_probe(True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**CONNECTION, "host": "192.0.2.9"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_cannot_connect(hass: HomeAssistant) -> None:
    write_device_file(hass)
    entry = make_entry()
    entry.add_to_hass(hass)

    result = await start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DEVICE_STEP
    )
    result = await pick(hass, result, "reconfigure_connection")
    with patch_probe(False):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONNECTION
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_connection"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow(hass: HomeAssistant) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {OPTION_MIN_SCAN_INTERVAL: 10}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {OPTION_MIN_SCAN_INTERVAL: 10}


async def test_options_flow_defaults_to_device_scan_interval(
    hass: HomeAssistant,
) -> None:
    write_device_file(hass, "acme_x2.yaml", DEVICE_YAML_DEFAULTS)
    entry = make_entry(**{CONF_FILENAME: "acme_x2.yaml"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    # the device file's 'scan_interval: 15' seeds the floor default
    assert form_defaults(result)[OPTION_MIN_SCAN_INTERVAL] == 15


async def test_reconfigure_no_device_files_aborts(hass: HomeAssistant) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.modbus_connect.config_flow.async_load_all",
        AsyncMock(return_value=({}, {})),
    ):
        result = await start_reconfigure(hass, entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_device_files"


# --- regressions: option preservation, stale groups, host normalization ------


async def test_options_flow_preserves_other_options(hass: HomeAssistant) -> None:
    # Saving the polling form must not wipe the group selection: an options
    # flow's create_entry replaces the whole dict, so it has to merge.
    entry = make_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry, options={OPTION_ENABLED_GROUPS: ["extra"]}
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {OPTION_MIN_SCAN_INTERVAL: 10}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        OPTION_ENABLED_GROUPS: ["extra"],
        OPTION_MIN_SCAN_INTERVAL: 10,
    }


async def test_reconfigure_to_new_device_file_clears_group_selection(
    hass: HomeAssistant,
) -> None:
    write_device_file(hass)
    write_device_file(hass, "acme_x2.yaml", DEVICE_YAML_DEFAULTS)
    entry = make_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry,
        options={OPTION_ENABLED_GROUPS: ["stale"], OPTION_MIN_SCAN_INTERVAL: 10},
    )

    result = await start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FILENAME: "acme_x2.yaml", CONF_NAME: ""}
    )
    result = await pick(hass, result, "reconfigure_connection")
    with patch_probe(True), patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONNECTION
        )
        # run the scheduled entry reload while setup is still mocked; without
        # this it fires at teardown and opens a real socket
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    # a different file has different groups: the stale selection is dropped,
    # everything else survives
    assert OPTION_ENABLED_GROUPS not in entry.options
    assert entry.options[OPTION_MIN_SCAN_INTERVAL] == 10


async def test_reconfigure_same_device_file_keeps_group_selection(
    hass: HomeAssistant,
) -> None:
    write_device_file(hass)
    entry = make_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry, options={OPTION_ENABLED_GROUPS: ["extra"]}
    )

    result = await start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DEVICE_STEP
    )
    result = await pick(hass, result, "reconfigure_connection")
    with patch_probe(True), patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONNECTION
        )
        # run the scheduled entry reload while setup is still mocked; without
        # this it fires at teardown and opens a real socket
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert entry.options[OPTION_ENABLED_GROUPS] == ["extra"]


def test_unique_id_normalizes_host() -> None:
    connection = {"host": " GW.Local ", "port": 502, CONF_SLAVE_ID: 7}
    assert _unique_id(connection) == "gw.local:502:7"


# --- serial transport ---------------------------------------------------------

SERIAL_CONNECTION = {
    CONF_SERIAL_PORT: "/dev/ttyUSB0",
    CONF_BAUDRATE: "19200",
    CONF_BYTESIZE: "8",
    CONF_PARITY: "e",  # the form's option values are lowercase translation keys
    CONF_STOPBITS: "1",
    CONF_SLAVE_ID: 7,
    CONF_PREFIX: "",
}


def patch_serial_probe(result: bool):
    return patch(
        "custom_components.modbus_connect.config_flow.async_probe_serial_device",
        return_value=None if result else "cannot_connect",
    )


def patch_ports():
    return patch(
        "custom_components.modbus_connect.config_flow._list_serial_ports",
        return_value=["/dev/ttyUSB0"],
    )


async def test_connection_type_menu_shown(hass: HomeAssistant) -> None:
    write_device_file(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DEVICE_STEP
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "connection_type"
    assert result["menu_options"] == ["connection", "serial"]


async def test_full_serial_flow(hass: HomeAssistant) -> None:
    write_device_file(hass)
    with patch_serial_probe(True), patch_ports(), patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], DEVICE_STEP
        )
        result = await pick(hass, result, "serial")
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "serial"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SERIAL_CONNECTION
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = result["data"]
    assert data[CONF_SERIAL_PORT] == "/dev/ttyUSB0"
    assert data[CONF_BAUDRATE] == 19200  # select strings coerced back to numbers
    assert data[CONF_BYTESIZE] == 8
    assert data[CONF_PARITY] == "E"  # "e" from the form, upper-cased for pymodbus
    assert data[CONF_STOPBITS] == 1
    assert "host" not in data
    assert result["result"].unique_id == "/dev/ttyUSB0:7"


async def test_serial_cannot_connect_shows_error(hass: HomeAssistant) -> None:
    write_device_file(hass)
    with patch_ports():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], DEVICE_STEP
        )
        result = await pick(hass, result, "serial")
        with patch_serial_probe(False):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], SERIAL_CONNECTION
            )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_to_serial_replaces_connection_data(
    hass: HomeAssistant,
) -> None:
    # switching transport must not leave stale host/port keys in entry.data
    write_device_file(hass)
    entry = make_entry()
    entry.add_to_hass(hass)

    result = await start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DEVICE_STEP
    )
    result = await pick(hass, result, "reconfigure_serial")
    assert result["step_id"] == "reconfigure_serial"
    with patch_serial_probe(True), patch_ports(), patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SERIAL_CONNECTION
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_SERIAL_PORT] == "/dev/ttyUSB0"
    assert "host" not in entry.data
    assert entry.unique_id == "/dev/ttyUSB0:7"


async def test_wrong_modbus_id_gets_pointed_error(hass: HomeAssistant) -> None:
    # gateway reachable but the device silent: not "cannot_connect" but a
    # message pointing straight at the Modbus ID
    write_device_file(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DEVICE_STEP
    )
    result = await pick(hass, result, "connection")
    with patch(
        "custom_components.modbus_connect.config_flow.async_probe_device",
        return_value="device_no_answer",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONNECTION
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "device_no_answer"}


def test_probe_span_picks_smallest_reader() -> None:
    from custom_components.modbus_connect.models import Span
    from custom_components.modbus_connect.schema import parse_device

    dev = parse_device(
        {
            "device": {"manufacturer": "A", "model": "X"},
            "holding": {
                "big": {"address": 0, "type": "uint32", "ha": {"platform": "sensor"}},
                "small": {"address": 9, "ha": {"platform": "sensor"}},
                "push": {"address": 4, "write_value": 1, "ha": {"platform": "button"}},
            },
        },
        "t.yaml",
    )
    assert _probe_span(dev) == Span("holding", 9, 1)

    # a file that never polls (button only) has no span to probe
    buttons_only = parse_device(
        {
            "device": {"manufacturer": "A", "model": "X"},
            "holding": {
                "push": {"address": 4, "write_value": 1, "ha": {"platform": "button"}}
            },
        },
        "t.yaml",
    )
    assert _probe_span(buttons_only) is None


async def test_write_only_file_falls_back_to_tcp_probe(hass: HomeAssistant) -> None:
    # nothing polls in this file, so there is nothing safe to read: the flow
    # only checks that the gateway accepts a TCP connection
    write_device_file(
        hass,
        "buttons.yaml",
        """
device:
  manufacturer: Acme
  model: Push
holding:
  push:
    address: 4
    write_value: 1
    ha:
      platform: button
      name: Push
""",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FILENAME: "buttons.yaml", CONF_NAME: ""}
    )
    result = await pick(hass, result, "connection")
    with (
        patch(
            "custom_components.modbus_connect.config_flow.async_probe",
            return_value=True,
        ),
        patch_setup(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONNECTION
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_framer_defaults_to_modbus_tcp(hass: HomeAssistant) -> None:
    # entries created without touching the protocol field store plain Modbus TCP
    write_device_file(hass)
    with patch_probe(True), patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], DEVICE_STEP
        )
        result = await pick(hass, result, "connection")
        submission = {k: v for k, v in CONNECTION.items() if k != CONF_FRAMER}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], submission
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_FRAMER] == FRAMER_SOCKET


async def test_rtu_over_tcp_framer_stored(hass: HomeAssistant) -> None:
    write_device_file(hass)
    with patch_probe(True), patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], DEVICE_STEP
        )
        result = await pick(hass, result, "connection")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**CONNECTION, CONF_FRAMER: FRAMER_RTU}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_FRAMER] == FRAMER_RTU
    # framing does not identify a different device
    assert result["result"].unique_id == UNIQUE_ID
