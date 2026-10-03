"""Config flow for Omnik Inverter integration."""


import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_SERIAL_NUMBER,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SERIAL_NUMBER,
)
from .omnik import OmnikConnectionError, OmnikInverter

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
        vol.Required(
            CONF_PORT, default=DEFAULT_PORT
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=65535,
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Required(CONF_SERIAL_NUMBER): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=MAX_SERIAL_NUMBER,
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Optional(
            CONF_NAME, default=DEFAULT_NAME
        ): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=10,
                max=3600,
                unit_of_measurement="seconds",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
    }
)


class OmnikInverterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Omnik Inverter."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._user_input: dict[str, Any] = {}

    def _create_entry(self) -> ConfigFlowResult:
        """Create the config entry from the stored user input."""
        user_input = self._user_input
        # Store connection details in data, user preferences in options
        return self.async_create_entry(
            title=user_input.get(CONF_NAME, DEFAULT_NAME),
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: int(user_input[CONF_PORT]),
                CONF_SERIAL_NUMBER: int(user_input[CONF_SERIAL_NUMBER]),
            },
            options={
                CONF_SCAN_INTERVAL: user_input.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._user_input = user_input

            # Create unique ID based on serial number (the selector returns a float,
            # keep that format so existing entries are still recognized)
            await self.async_set_unique_id(str(user_input[CONF_SERIAL_NUMBER]))
            self._abort_if_unique_id_configured()

            inverter = OmnikInverter(
                host=user_input[CONF_HOST],
                port=int(user_input[CONF_PORT]),
                serial_number=int(user_input[CONF_SERIAL_NUMBER]),
            )
            try:
                await inverter.async_test_connection()
            except OmnikConnectionError as err:
                _LOGGER.debug("Connection test failed: %s", err)
                # The inverter may just be offline (e.g., at night), let the user decide
                return await self.async_step_cannot_connect()

            return self._create_entry()

        # Show configuration form, pre-filled when retrying
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, self._user_input
            ),
        )

    async def async_step_cannot_connect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user retry or add an inverter that is currently offline."""
        return self.async_show_menu(
            step_id="cannot_connect",
            menu_options=["user", "add_offline"],
            description_placeholders={
                "host": self._user_input[CONF_HOST],
                "port": str(int(self._user_input[CONF_PORT])),
            },
        )

    async def async_step_add_offline(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add the inverter without a successful connection test."""
        return self._create_entry()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OmnikInverterOptionsFlow()


class OmnikInverterOptionsFlow(OptionsFlow):
    """Handle options flow for Omnik Inverter."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10,
                            max=3600,
                            unit_of_measurement="seconds",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
