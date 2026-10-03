"""Constants for the Omnik Inverter integration."""


from typing import Final

DOMAIN: Final = "omnik_inverter"

# Configuration keys
CONF_SERIAL_NUMBER: Final = "serial_number"

# Defaults
DEFAULT_NAME: Final = "Omnik"
DEFAULT_PORT: Final = 8899
DEFAULT_SCAN_INTERVAL: Final = 60
DEFAULT_TIMEOUT: Final = 10

# The serial number is sent to the inverter as a 4-byte value
MAX_SERIAL_NUMBER: Final = 0xFFFFFFFF

# Platforms
PLATFORMS: Final = ["sensor"]
