"""Tests for the Omnik TCP protocol module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.omnik_inverter import omnik
from custom_components.omnik_inverter.omnik import OmnikConnectionError, OmnikInverter

from .conftest import SERIAL_NUMBER, build_message


def _inverter(raw: bytes | None = None) -> OmnikInverter:
    inverter = OmnikInverter("192.168.1.50", 8899, SERIAL_NUMBER, timeout=1)
    inverter._raw_msg = raw
    return inverter


def _legacy_request(serial_number: int) -> bytes:
    """Request as built by the original hex-string based implementation."""
    serial_bytes = bytearray.fromhex(hex(serial_number)[2:] * 2)
    serial_bytes.reverse()
    checksum = (115 + sum(serial_bytes)) & 0xFF
    return bytes([0x68, 0x02, 0x40, 0x30, *serial_bytes, 0x01, 0x00, checksum, 0x16])


@pytest.mark.parametrize("serial_number", [602123456, 1601234567, 0x10000000, 0xFFFFFFFF])
def test_generate_request_matches_legacy(serial_number: int) -> None:
    """The request is identical to the original implementation for 8-digit hex serials."""
    assert OmnikInverter._generate_request(serial_number) == _legacy_request(serial_number)


def test_generate_request_layout() -> None:
    """The request has the expected framing and little-endian doubled serial."""
    request = OmnikInverter._generate_request(SERIAL_NUMBER)
    serial = SERIAL_NUMBER.to_bytes(4, "little")
    assert len(request) == 16
    assert request[:4] == b"\x68\x02\x40\x30"
    assert request[4:12] == serial * 2
    assert request[12:14] == b"\x01\x00"
    assert request[14] == (115 + 2 * sum(serial)) & 0xFF
    assert request[15] == 0x16


def test_generate_request_short_serial() -> None:
    """A serial with an odd number of hex digits no longer raises."""
    assert len(OmnikInverter._generate_request(0x1234567)) == 16


def test_parse_single_string() -> None:
    """A single-string, single-phase response leaves the other slots None."""
    data = _inverter(build_message())._parse_data()

    assert data.status == "Online"
    assert data.serial_number == "NLDN1234567890AB"
    assert data.temperature == 32.1
    assert data.actual_power == 700
    assert data.energy_today == 1.23
    assert data.energy_total == 9876.5
    assert data.hours_total == 4321
    assert data.dc_input_voltage == 250.0
    assert data.dc_input_current == 1.5
    assert data.ac_output_voltage == 230.1
    assert data.ac_output_current == 3.0
    assert data.ac_output_frequency == 50.01
    assert data.ac_output_power == 700
    for field in (
        "dc_input_voltage",
        "dc_input_current",
        "ac_output_voltage",
        "ac_output_current",
        "ac_output_frequency",
        "ac_output_power",
    ):
        assert getattr(data, f"{field}_2") is None
        assert getattr(data, f"{field}_3") is None


def test_parse_three_strings_three_phases() -> None:
    """All string and phase slots are read from the right offsets."""
    data = _inverter(build_message(strings=3, phases=3))._parse_data()

    assert (data.dc_input_voltage, data.dc_input_voltage_2, data.dc_input_voltage_3) == (
        250.0,
        240.0,
        230.0,
    )
    assert (data.dc_input_current, data.dc_input_current_2, data.dc_input_current_3) == (
        1.5,
        1.4,
        1.3,
    )
    assert (data.ac_output_voltage, data.ac_output_voltage_2, data.ac_output_voltage_3) == (
        230.1,
        230.2,
        230.3,
    )
    assert (data.ac_output_current, data.ac_output_current_2, data.ac_output_current_3) == (
        3.0,
        3.1,
        3.2,
    )
    assert (
        data.ac_output_frequency,
        data.ac_output_frequency_2,
        data.ac_output_frequency_3,
    ) == (50.01, 50.02, 50.03)
    assert (data.ac_output_power, data.ac_output_power_2, data.ac_output_power_3) == (
        700,
        710,
        720,
    )


def test_parse_invalid_temperature() -> None:
    """Temperatures above 150°C are treated as invalid."""
    msg = bytearray(build_message())
    msg[31:33] = (2000).to_bytes(2, "big")
    assert _inverter(bytes(msg))._parse_data().temperature is None


@pytest.mark.parametrize("raw", [None, b"", b"\x00" * 40])
def test_parse_short_message(raw: bytes | None) -> None:
    """A missing or too short response yields an Offline result without values."""
    data = _inverter(raw)._parse_data()

    assert data.status == "Offline"
    assert data.actual_power == 0
    assert data.energy_total is None
    assert data.dc_input_voltage_2 is None


def _mock_stream(response: bytes | Exception) -> tuple[MagicMock, MagicMock]:
    reader = MagicMock()
    reader.read = AsyncMock(side_effect=[response])
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    return reader, writer


async def test_get_data_success() -> None:
    """Data is fetched over TCP, parsed and the connection closed."""
    reader, writer = _mock_stream(build_message(strings=2))
    inverter = _inverter()

    with patch.object(omnik.asyncio, "open_connection", AsyncMock(return_value=(reader, writer))):
        data = await inverter.async_get_data()

    writer.write.assert_called_once_with(OmnikInverter._generate_request(SERIAL_NUMBER))
    writer.close.assert_called_once()
    assert data.status == "Online"
    assert data.dc_input_voltage_2 == 240.0


@pytest.mark.parametrize("error", [TimeoutError(), ConnectionRefusedError("refused")])
async def test_get_data_connect_failure_retries(error: Exception) -> None:
    """Connection failures are retried and end in OmnikConnectionError."""
    open_connection = AsyncMock(side_effect=error)

    with (
        patch.object(omnik.asyncio, "open_connection", open_connection),
        patch.object(omnik.asyncio, "sleep", AsyncMock()) as sleep,
        pytest.raises(OmnikConnectionError),
    ):
        await _inverter().async_get_data()

    assert open_connection.await_count == omnik.MAX_RETRIES
    assert sleep.await_count == omnik.MAX_RETRIES - 1


@pytest.mark.parametrize("response", [b"", TimeoutError(), ConnectionResetError("reset")])
async def test_single_fetch_read_failure(response: bytes | Exception) -> None:
    """An empty reply, timeout or reset while reading raises and closes the socket."""
    reader, writer = _mock_stream(response)

    with (
        patch.object(omnik.asyncio, "open_connection", AsyncMock(return_value=(reader, writer))),
        pytest.raises(OmnikConnectionError),
    ):
        await _inverter()._async_single_fetch()

    writer.close.assert_called_once()


async def test_retry_then_success() -> None:
    """A transient failure is followed by a successful retry."""
    reader, writer = _mock_stream(build_message())
    open_connection = AsyncMock(side_effect=[OSError("unreachable"), (reader, writer)])

    with (
        patch.object(omnik.asyncio, "open_connection", open_connection),
        patch.object(omnik.asyncio, "sleep", AsyncMock()),
    ):
        data = await _inverter().async_get_data()

    assert data.status == "Online"


async def test_test_connection_single_attempt() -> None:
    """The connection test does not retry."""
    open_connection = AsyncMock(side_effect=OSError("unreachable"))

    with (
        patch.object(omnik.asyncio, "open_connection", open_connection),
        pytest.raises(OmnikConnectionError),
    ):
        await _inverter().async_test_connection()

    assert open_connection.await_count == 1
