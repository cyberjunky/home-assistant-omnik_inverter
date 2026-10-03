"""Tests for the Omnik Inverter config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.omnik_inverter.const import CONF_SERIAL_NUMBER, DOMAIN
from custom_components.omnik_inverter.omnik import OmnikConnectionError, OmnikInverter

from .conftest import ENTRY_DATA, SERIAL_NUMBER

USER_INPUT = {
    CONF_HOST: "192.168.1.50",
    CONF_PORT: 8899,
    CONF_SERIAL_NUMBER: SERIAL_NUMBER,
    CONF_NAME: "Roof",
    CONF_SCAN_INTERVAL: 30,
}


@pytest.fixture
def mock_test_connection() -> Generator[AsyncMock]:
    """Patch the connection test of the inverter."""
    with patch.object(OmnikInverter, "async_test_connection", AsyncMock(return_value=True)) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent the config entry from actually being set up."""
    with patch(
        "custom_components.omnik_inverter.async_setup_entry", AsyncMock(return_value=True)
    ) as mock:
        yield mock


async def test_user_flow_success(hass: HomeAssistant, mock_test_connection: AsyncMock) -> None:
    """A reachable inverter is added directly."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Roof"
    assert result["data"] == ENTRY_DATA
    assert result["options"] == {CONF_SCAN_INTERVAL: 30}
    assert isinstance(result["data"][CONF_SERIAL_NUMBER], int)
    mock_test_connection.assert_awaited_once()


async def test_user_flow_offline_add_anyway(
    hass: HomeAssistant, mock_test_connection: AsyncMock
) -> None:
    """An unreachable inverter can still be added."""
    mock_test_connection.side_effect = OmnikConnectionError("offline")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "cannot_connect"
    assert result["menu_options"] == ["user", "add_offline"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_offline"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == ENTRY_DATA


async def test_user_flow_offline_retry(
    hass: HomeAssistant, mock_test_connection: AsyncMock
) -> None:
    """After a failed test the user can correct the settings and retry."""
    mock_test_connection.side_effect = OmnikConnectionError("offline")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={**USER_INPUT, CONF_HOST: "192.168.1.99"}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_test_connection.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.168.1.50"


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_test_connection: AsyncMock
) -> None:
    """The same serial number cannot be added twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_test_connection.assert_not_awaited()


async def test_options_flow(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """The update interval can be changed."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 120}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_SCAN_INTERVAL: 120}
