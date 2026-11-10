"""Shared test fixtures."""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import get_test_config_dir

# Make `custom_components.modbus_connect` importable from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load the integration in every test."""
    return


@pytest.fixture(autouse=True)
def clean_user_device_dir() -> Iterator[None]:
    """Start and leave every test with an empty user device-file directory.

    Home Assistant's test config dir is one real directory shared by all tests
    (and all runs); without this, a device file one test writes is still there
    for the next, and tests pass or fail depending on their order.
    """
    directory = Path(get_test_config_dir("modbus_connect"))

    def wipe() -> None:
        for path in directory.glob("*.yaml"):
            path.unlink()

    wipe()
    yield
    wipe()

