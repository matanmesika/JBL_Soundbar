"""Tests for JBL equalizer helpers."""

from __future__ import annotations

import pytest

from custom_components.jbl_integration.equalizer import (
    build_eq_request,
    normalize_eq_gains,
)


def test_new_firmware_eq_curve_is_quantized_and_clamped() -> None:
    """Seven-band EQ uses 0.5 dB steps and per-band limits."""
    gains = [-20, -5.74, -0.26, 0.24, 1.26, 7.0, 3.74]

    result = normalize_eq_gains(True, gains)

    assert result == [-9.0, -5.5, -0.5, 0.0, 1.5, 6.0, 3.5]


def test_legacy_eq_curve_is_quantized_and_clamped() -> None:
    """Legacy three-band EQ uses whole dB values and +/-6 dB limits."""
    gains = [-8.2, 1.6, 9.2]

    result = normalize_eq_gains(False, gains)

    assert result == [-6.0, 2.0, 6.0]


@pytest.mark.parametrize(
    ("new_firmware", "gains", "expected"),
    [
        (True, [0, 0, 0], "Expected 7 EQ gains"),
        (False, [0, 0, 0, 0], "Expected 3 EQ gains"),
    ],
)
def test_eq_curve_rejects_wrong_band_count(
    new_firmware: bool,
    gains: list[float],
    expected: str,
) -> None:
    """The integration must not send malformed EQ curves to the soundbar."""
    with pytest.raises(ValueError, match=expected):
        normalize_eq_gains(new_firmware, gains)


def test_build_new_firmware_eq_request() -> None:
    """Build a complete seven-band setActiveEQ request."""
    command, body, keys, normalized = build_eq_request(
        True, [0, 0.5, 1, 1.5, 2, 2.5, 3]
    )

    assert command == "setActiveEQ"
    assert body["active_eq_id"] == "0"
    assert body["band"] == 7
    assert body["eq_payload"]["fs"] == [
        125.0,
        250.0,
        500.0,
        1000.0,
        2000.0,
        4000.0,
        8000.0,
    ]
    assert body["eq_payload"]["gain"] == normalized
    assert keys == (
        "125Hz",
        "250Hz",
        "500Hz",
        "1000Hz",
        "2000Hz",
        "4000Hz",
        "8000Hz",
    )


def test_build_legacy_eq_request() -> None:
    """Build a complete legacy three-band setEQ request."""
    command, body, keys, normalized = build_eq_request(False, [-2, 0, 4])

    assert command == "setEQ"
    assert body["eq_name"] == "Custom"
    assert body["eq_status"] == "on"
    assert body["eq_payload"]["fs"] == [150.0, 1000.0, 6000.0]
    assert body["eq_payload"]["gain"] == normalized
    assert keys == ("EQ_1_Low", "EQ_2_Mid", "EQ_3_High")
