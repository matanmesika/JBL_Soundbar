"""Equalizer helpers shared by the JBL coordinator and tests."""

from __future__ import annotations

from typing import Any

NEW_EQ_KEYS = ("125Hz", "250Hz", "500Hz", "1000Hz", "2000Hz", "4000Hz", "8000Hz")
NEW_EQ_FREQUENCIES = (125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0)
NEW_EQ_MINIMUMS = (-9.0, -6.0, -6.0, -6.0, -6.0, -6.0, -6.0)
NEW_EQ_MAXIMUMS = (6.0,) * 7

LEGACY_EQ_KEYS = ("EQ_1_Low", "EQ_2_Mid", "EQ_3_High")
LEGACY_EQ_FREQUENCIES = (150.0, 1000.0, 6000.0)


def normalize_eq_gains(new_firmware: bool, gains: list[float]) -> list[float]:
    """Validate, clamp and quantize EQ gain values."""
    expected = 7 if new_firmware else 3
    if len(gains) != expected:
        raise ValueError(f"Expected {expected} EQ gains, got {len(gains)}")

    if new_firmware:
        return [
            max(
                NEW_EQ_MINIMUMS[index],
                min(NEW_EQ_MAXIMUMS[index], round(float(value) * 2) / 2),
            )
            for index, value in enumerate(gains)
        ]

    return [max(-6.0, min(6.0, float(round(float(value))))) for value in gains]


def build_eq_request(
    new_firmware: bool, gains: list[float]
) -> tuple[str, dict[str, Any], tuple[str, ...], list[float]]:
    """Build the JBL API command and payload for a complete EQ curve."""
    normalized = normalize_eq_gains(new_firmware, gains)

    if new_firmware:
        return (
            "setActiveEQ",
            {
                "active_eq_id": "0",
                "band": 7,
                "eq_payload": {
                    "fs": list(NEW_EQ_FREQUENCIES),
                    "gain": normalized,
                },
            },
            NEW_EQ_KEYS,
            normalized,
        )

    return (
        "setEQ",
        {
            "eq_id": "1",
            "eq_name": "Custom",
            "eq_payload": {
                "fs": list(LEGACY_EQ_FREQUENCIES),
                "gain": normalized,
                "q": [0.7070000171661377, 0.5, 0.7070000171661377],
                "type": [17.0, 11.0, 16.0],
            },
            "eq_status": "on",
        },
        LEGACY_EQ_KEYS,
        normalized,
    )
