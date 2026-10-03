"""Fixtures for Omnik Inverter tests."""

import struct

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.omnik_inverter.const import CONF_SERIAL_NUMBER, DOMAIN

SERIAL_NUMBER = 602123456

ENTRY_DATA = {
    CONF_HOST: "192.168.1.50",
    CONF_PORT: 8899,
    CONF_SERIAL_NUMBER: SERIAL_NUMBER,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of the custom integration in all tests."""
    return


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Omnik",
        data=dict(ENTRY_DATA),
        options={CONF_SCAN_INTERVAL: 60},
        unique_id=str(float(SERIAL_NUMBER)),
    )


def build_message(*, strings: int = 1, phases: int = 1) -> bytes:
    """Build an inverter response; unused string/phase slots read as 0xFFFF."""
    msg = bytearray(b"\xff" * 100)
    msg[15:31] = b"NLDN1234567890AB"

    def put_short(offset: int, value: int) -> None:
        msg[offset : offset + 2] = struct.pack("!H", value)

    put_short(31, 321)  # temperature 32.1
    for i in range(strings):
        put_short(33 + i * 2, 2500 - i * 100)  # PV voltage 250.0, 240.0, 230.0
        put_short(39 + i * 2, 15 - i)  # PV current 1.5, 1.4, 1.3
    for i in range(phases):
        put_short(45 + i * 2, 30 + i)  # AC current 3.0, 3.1, 3.2
        put_short(51 + i * 2, 2301 + i)  # AC voltage 230.1, 230.2, 230.3
        put_short(57 + i * 4, 5001 + i)  # AC frequency 50.01, 50.02, 50.03
        put_short(59 + i * 4, 700 + i * 10)  # AC power 700, 710, 720
    put_short(69, 123)  # energy today 1.23
    msg[71:75] = struct.pack("!I", 98765)  # energy total 9876.5
    msg[75:79] = struct.pack("!I", 4321)  # hours total
    return bytes(msg)
