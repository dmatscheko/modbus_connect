"""Config, reconfigure, and options flow tests."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import voluptuous as vol
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.modbus_connect.config_flow import _unique_id
from custom_components.modbus_connect.const import (
    CONF_FILENAME,
    CONF_PREFIX,
    CONF_SLAVE_ID,
    DOMAIN,
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
CONNECTION = {"host": "192.0.2.1", "port": 502, CONF_SLAVE_ID: 7, CONF_PREFIX: ""}
UNIQUE_ID = "192.0.2.1:502:7"


def write_device_file(
    hass: HomeAssistant, name: str = "acme_x1.yaml", content: str = DEVICE_YAML
) -> None:
    """Drop a minimal device file into the user config dir."""
    directory = Path(hass.config.config_dir) / DOMAIN
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(content, encoding="utf-8")


def patch_probe(result: bool):
    return patch(
        "custom_components.modbus_connect.config_flow.async_probe", return_value=result
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
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONNECTION
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_no_device_files_aborts(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.modbus_connect.config_flow.async_load_all",
        AsyncMock(return_value={}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_device_files"


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
        AsyncMock(return_value={}),
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
    with patch_probe(True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONNECTION
        )
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
    with patch_probe(True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONNECTION
        )
    assert result["type"] is FlowResultType.ABORT
    assert entry.options[OPTION_ENABLED_GROUPS] == ["extra"]


def test_unique_id_normalizes_host() -> None:
    connection = {"host": " GW.Local ", "port": 502, CONF_SLAVE_ID: 7}
    assert _unique_id(connection) == "gw.local:502:7"
