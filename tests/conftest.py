"""Shared test fixtures."""

import sys
from pathlib import Path

import pytest

# Make `custom_components.modbus_connect` importable from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load the integration in every test."""
    return
