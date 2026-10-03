"""Data update coordinator for Omnik Inverter."""


import logging
from dataclasses import replace
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SERIAL_NUMBER, DEFAULT_SCAN_INTERVAL, DOMAIN
from .omnik import OmnikConnectionError, OmnikInverter, OmnikInverterData

_LOGGER = logging.getLogger(__name__)


class OmnikDataUpdateCoordinator(DataUpdateCoordinator[OmnikInverterData]):
    """Class to manage fetching Omnik Inverter data."""

    config_entry: ConfigEntry
    _last_successful_data: OmnikInverterData | None = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.inverter = OmnikInverter(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            serial_number=int(entry.data[CONF_SERIAL_NUMBER]),
        )
        self._last_successful_data = None

        # Get scan interval from options, fall back to default
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> OmnikInverterData:
        """Fetch data from the inverter.

        When the inverter is offline (e.g., at night), returns the last known
        data with status set to "Offline" instead of marking entities unavailable.
        """
        try:
            data = await self.inverter.async_get_data()
            # Store successful data for fallback during offline periods
            self._last_successful_data = data
            return data
        except OmnikConnectionError as err:
            _LOGGER.debug("Inverter offline or unreachable: %s", err)

            # If we have previous data, return it with status set to Offline
            if self._last_successful_data is not None:
                _LOGGER.debug(
                    "Returning last known data with Offline status"
                )
                last = self._last_successful_data
                return replace(
                    last,
                    status="Offline",
                    actual_power=0,
                    ac_output_power=0,
                    # Phases the inverter doesn't have stay None
                    ac_output_power_2=None if last.ac_output_power_2 is None else 0,
                    ac_output_power_3=None if last.ac_output_power_3 is None else 0,
                )

            # No previous data available - must raise to indicate unavailable
            raise UpdateFailed(f"Error communicating with inverter: {err}") from err
