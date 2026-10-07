"""Tests for JBL equalizer helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


# Load the pure helper module directly so these unit tests stay lightweight and
# do not require importing the full Home Assistant integration package.
MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "jbl_integration"
    / "equalizer.py"
)
SPEC = importlib.util.spec_from_file_location("jbl_equalizer_helpers", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
equalizer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(equalizer)

build_eq_request = equalizer.build_eq_request
format_frequency = equalizer.format_frequency
normalize_eq_gains = equalizer.normalize_eq_gains


def test_dynamic_eq_curve_preserves_arbitrary_band_count() -> None:
    """The helper must not assume three or seven EQ bands."""
    frequencies = [60, 120, 250, 500, 1000, 2000, 4000, 8000, 12000, 16000]
    gains = [-2, -1.5, 0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5]

    command, body, normalized = build_eq_request(
        new_firmware=True,
        gains=gains,
        profile={
            "frequencies": frequencies,
            "band": len(frequencies),
            "step": 0.5,
        },
    )

    assert command == "setActiveEQ"
    assert body["band"] == 10
    assert body["eq_payload"]["fs"] == frequencies
    assert body["eq_payload"]["gain"] == gains
    assert normalized == gains


def test_device_defined_limits_and_step_are_respected() -> None:
    """Limits are driven by the device profile rather than fixed band rules."""
    result = normalize_eq_gains(
        [-20, -5.74, 0.24, 11],
        minimums=[-12, -8, -4, -10],
        maximums=[12, 8, 4, 10],
        step=0.5,
    )

    assert result == [-12.0, -5.5, 0.0, 10.0]


def test_no_limits_are_invented_when_device_does_not_report_them() -> None:
    """Unknown JBL models keep their reported range unrestricted."""
    result = normalize_eq_gains([-18.25, 0, 14.75])

    assert result == [-18.25, 0.0, 14.75]


def test_eq_curve_rejects_empty_curve() -> None:
    """An empty curve is invalid regardless of model."""
    with pytest.raises(ValueError, match="at least one band"):
        normalize_eq_gains([])


def test_eq_request_rejects_frequency_gain_length_mismatch() -> None:
    """A malformed device profile cannot result in a malformed API request."""
    with pytest.raises(ValueError, match="does not match"):
        build_eq_request(
            new_firmware=True,
            gains=[0, 1, 2],
            profile={"frequencies": [125, 250]},
        )


def test_new_firmware_request_preserves_device_payload_metadata() -> None:
    """Unknown payload fields such as Q/type survive graph edits."""
    original_payload = {
        "fs": [100, 500, 2000, 10000],
        "gain": [0, 0, 0, 0],
        "q": [0.7, 0.8, 0.9, 1.0],
        "type": [17, 11, 11, 16],
        "future_field": ["keep", "me"],
    }

    command, body, normalized = build_eq_request(
        new_firmware=True,
        gains=[1, 2, 3, 4],
        profile={
            "frequencies": original_payload["fs"],
            "band": 4,
            "active_eq_id": "2",
            "eq_payload": original_payload,
        },
    )

    assert command == "setActiveEQ"
    assert body["active_eq_id"] == "2"
    assert body["band"] == 4
    assert body["eq_payload"]["q"] == original_payload["q"]
    assert body["eq_payload"]["type"] == original_payload["type"]
    assert body["eq_payload"]["future_field"] == ["keep", "me"]
    assert body["eq_payload"]["gain"] == normalized


def test_legacy_request_still_supports_classic_three_band_devices() -> None:
    """Classic JBL EQ remains backwards compatible."""
    command, body, normalized = build_eq_request(
        new_firmware=False,
        gains=[-2, 0, 4],
        profile={
            "frequencies": [150, 1000, 6000],
            "step": 1,
            "minimums": [-6, -6, -6],
            "maximums": [6, 6, 6],
        },
    )

    assert command == "setEQ"
    assert body["eq_name"] == "Custom"
    assert body["eq_status"] == "on"
    assert body["eq_payload"]["fs"] == [150, 1000, 6000]
    assert body["eq_payload"]["gain"] == [-2.0, 0.0, 4.0]
    assert normalized == [-2.0, 0.0, 4.0]


@pytest.mark.parametrize(
    ("frequency", "expected"),
    [
        (125, "125 Hz"),
        (500, "500 Hz"),
        (1000, "1 kHz"),
        (2000, "2 kHz"),
        (16000, "16 kHz"),
        (1250, "1250 Hz"),
    ],
)
def test_frequency_labels_are_dynamic(frequency: float, expected: str) -> None:
    """The card labels any frequency layout reported by a JBL device."""
    assert format_frequency(frequency) == expected
