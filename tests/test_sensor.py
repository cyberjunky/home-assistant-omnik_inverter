"""Tests for the Omnik Inverter sensors and coordinator fallback."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.omnik_inverter.const import DOMAIN
from custom_components.omnik_inverter.coordinator import OmnikDataUpdateCoordinator
from custom_components.omnik_inverter.omnik import OmnikConnectionError, OmnikInverter

from .conftest import SERIAL_NUMBER, build_message

BASE_SENSOR_COUNT = 13


async def _setup(
    hass: HomeAssistant, entry: MockConfigEntry, fetch: AsyncMock
) -> OmnikDataUpdateCoordinator:
    entry.add_to_hass(hass)
    with patch.object(OmnikInverter, "_async_fetch_data", fetch):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id]


async def _refresh(
    hass: HomeAssistant, coordinator: OmnikDataUpdateCoordinator, fetch: AsyncMock
) -> None:
    with patch.object(OmnikInverter, "_async_fetch_data", fetch):
        await coordinator.async_refresh()
        await hass.async_block_till_done()


async def test_single_string_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A single-string inverter only gets the base sensors."""
    await _setup(hass, mock_config_entry, AsyncMock(return_value=build_message()))

    entity_ids = hass.states.async_entity_ids("sensor")
    assert len(entity_ids) == BASE_SENSOR_COUNT
    assert not any(entity_id.endswith(("_2", "_3")) for entity_id in entity_ids)

    assert hass.states.get("sensor.omnik_status").state == "Online"
    assert hass.states.get("sensor.omnik_actual_power").state == "700"
    assert hass.states.get("sensor.omnik_energy_today").state == "1.23"
    assert hass.states.get("sensor.omnik_energy_total").state == "9876.5"
    assert hass.states.get("sensor.omnik_hours_total").state == "4321"
    assert hass.states.get("sensor.omnik_inverter_serial_number").state == "NLDN1234567890AB"
    assert hass.states.get("sensor.omnik_temperature").state == "32.1"
    assert hass.states.get("sensor.omnik_dc_input_voltage").state == "250.0"
    assert hass.states.get("sensor.omnik_dc_input_current").state == "1.5"
    assert hass.states.get("sensor.omnik_ac_output_voltage").state == "230.1"
    assert hass.states.get("sensor.omnik_ac_output_current").state == "3.0"
    assert hass.states.get("sensor.omnik_ac_output_frequency").state == "50.01"
    assert hass.states.get("sensor.omnik_ac_output_power").state == "700"


async def test_device_and_unique_ids(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Sensors share one device and use the serial number in their unique IDs."""
    await _setup(hass, mock_config_entry, AsyncMock(return_value=build_message()))

    entry = er.async_get(hass).async_get("sensor.omnik_actual_power")
    assert entry is not None
    assert entry.unique_id == f"{SERIAL_NUMBER}_actual_power"

    device = dr.async_get(hass).async_get(entry.device_id)
    assert device is not None
    assert device.identifiers == {(DOMAIN, str(SERIAL_NUMBER))}
    assert device.name == "Omnik"
    assert device.manufacturer == "Omnik"

    entity_entries = er.async_entries_for_config_entry(er.async_get(hass), mock_config_entry.entry_id)
    assert {e.device_id for e in entity_entries} == {device.id}


async def test_two_string_sensors(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """A second PV string adds only its voltage and current sensors."""
    await _setup(hass, mock_config_entry, AsyncMock(return_value=build_message(strings=2)))

    assert len(hass.states.async_entity_ids("sensor")) == BASE_SENSOR_COUNT + 2
    assert hass.states.get("sensor.omnik_dc_input_voltage_2").state == "240.0"
    assert hass.states.get("sensor.omnik_dc_input_current_2").state == "1.4"
    assert hass.states.get("sensor.omnik_dc_input_voltage_3") is None
    assert hass.states.get("sensor.omnik_ac_output_power_2") is None


async def test_three_phase_sensors(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """A three-string, three-phase inverter gets all sensors."""
    await _setup(
        hass, mock_config_entry, AsyncMock(return_value=build_message(strings=3, phases=3))
    )

    assert len(hass.states.async_entity_ids("sensor")) == BASE_SENSOR_COUNT + 12
    assert hass.states.get("sensor.omnik_dc_input_voltage_3").state == "230.0"
    assert hass.states.get("sensor.omnik_ac_output_voltage_2").state == "230.2"
    assert hass.states.get("sensor.omnik_ac_output_current_3").state == "3.2"
    assert hass.states.get("sensor.omnik_ac_output_frequency_2").state == "50.02"
    assert hass.states.get("sensor.omnik_ac_output_power_3").state == "720"


async def test_sensors_added_when_reported_later(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Strings that first show up in a later response get their sensors then."""
    coordinator = await _setup(hass, mock_config_entry, AsyncMock(return_value=build_message()))
    assert len(hass.states.async_entity_ids("sensor")) == BASE_SENSOR_COUNT

    await _refresh(hass, coordinator, AsyncMock(return_value=build_message(strings=2)))
    assert len(hass.states.async_entity_ids("sensor")) == BASE_SENSOR_COUNT + 2

    # No duplicates on further updates
    await _refresh(hass, coordinator, AsyncMock(return_value=build_message(strings=2)))
    assert len(hass.states.async_entity_ids("sensor")) == BASE_SENSOR_COUNT + 2


async def test_offline_keeps_last_values(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """When the inverter goes offline, power drops to 0 and totals are kept."""
    coordinator = await _setup(
        hass, mock_config_entry, AsyncMock(return_value=build_message(strings=2, phases=3))
    )

    await _refresh(hass, coordinator, AsyncMock(side_effect=OmnikConnectionError("offline")))

    assert coordinator.last_update_success
    assert hass.states.get("sensor.omnik_status").state == "Offline"
    assert hass.states.get("sensor.omnik_actual_power").state == "0"
    assert hass.states.get("sensor.omnik_ac_output_power").state == "0"
    assert hass.states.get("sensor.omnik_ac_output_power_2").state == "0"
    assert hass.states.get("sensor.omnik_ac_output_power_3").state == "0"
    assert hass.states.get("sensor.omnik_energy_total").state == "9876.5"
    assert hass.states.get("sensor.omnik_energy_today").state == "1.23"

    # Back online
    await _refresh(
        hass, coordinator, AsyncMock(return_value=build_message(strings=2, phases=3))
    )
    assert hass.states.get("sensor.omnik_status").state == "Online"
    assert hass.states.get("sensor.omnik_ac_output_power_3").state == "720"


async def test_offline_single_phase_keeps_unused_phases_none(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Offline fallback does not invent values for phases the inverter lacks."""
    coordinator = await _setup(hass, mock_config_entry, AsyncMock(return_value=build_message()))

    await _refresh(hass, coordinator, AsyncMock(side_effect=OmnikConnectionError("offline")))

    assert coordinator.data.ac_output_power_2 is None
    assert coordinator.data.ac_output_power_3 is None
    assert len(hass.states.async_entity_ids("sensor")) == BASE_SENSOR_COUNT
