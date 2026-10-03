"""Tests for setting up and unloading the Omnik Inverter integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.omnik_inverter.const import DOMAIN
from custom_components.omnik_inverter.omnik import OmnikConnectionError, OmnikInverter

from .conftest import build_message


async def test_setup_and_unload(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """The entry is set up with the configured interval and unloads cleanly."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(OmnikInverter, "_async_fetch_data", AsyncMock(return_value=build_message())):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.update_interval == timedelta(seconds=60)
    assert coordinator.config_entry is mock_config_entry

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]


async def test_setup_retry_when_offline(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Without any previous data an offline inverter leads to a setup retry."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(
        OmnikInverter, "_async_fetch_data", AsyncMock(side_effect=OmnikConnectionError("offline"))
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
