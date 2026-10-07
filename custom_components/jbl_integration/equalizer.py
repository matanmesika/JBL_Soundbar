"""Equalizer helpers shared by the JBL coordinator and tests."""

from __future__ import annotations

from typing import Any

LEGACY_EQ_FREQUENCIES = (150.0, 1000.0, 6000.0)


def format_frequency(value: float) -> str:
    """Format an arbitrary EQ frequency for the frontend."""
    frequency = float(value)
    if frequency >= 1000 and frequency % 1000 == 0:
        return f"{frequency / 1000:g} kHz"
    return f"{frequency:g} Hz"


def normalize_eq_gains(
    gains: list[float],
    *,
    minimums: list[float] | None = None,
    maximums: list[float] | None = None,
    step: float | None = None,
) -> list[float]:
    """Clamp/quantize an arbitrary number of EQ bands.

    No band count or frequency layout is assumed. Limits and step are applied
    only when the device/profile exposes them.
    """
    values = [float(value) for value in gains]
    if not values:
        raise ValueError("EQ curve must contain at least one band")

    if minimums is not None and len(minimums) != len(values):
        raise ValueError("EQ minimums must match the gain count")
    if maximums is not None and len(maximums) != len(values):
        raise ValueError("EQ maximums must match the gain count")

    normalized: list[float] = []
    for index, value in enumerate(values):
        if step and step > 0:
            value = round(value / step) * step
        if minimums is not None:
            value = max(float(minimums[index]), value)
        if maximums is not None:
            value = min(float(maximums[index]), value)
        normalized.append(value)
    return normalized


def build_eq_request(
    *,
    new_firmware: bool,
    gains: list[float],
    profile: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any], list[float]]:
    """Build a complete EQ request while preserving device-provided metadata."""
    profile = profile or {}
    frequencies = list(profile.get("frequencies") or [])
    minimums = profile.get("minimums")
    maximums = profile.get("maximums")
    step = profile.get("step")

    if not frequencies:
        frequencies = (
            [125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0]
            if new_firmware
            else list(LEGACY_EQ_FREQUENCIES)
        )

    if len(frequencies) != len(gains):
        raise ValueError(
            f"EQ frequency count ({len(frequencies)}) does not match "
            f"gain count ({len(gains)})"
        )

    normalized = normalize_eq_gains(
        gains,
        minimums=minimums,
        maximums=maximums,
        step=step,
    )

    # Preserve every device-supplied payload field (Q, filter types, etc.) and
    # replace only the values the editor owns.
    eq_payload = dict(profile.get("eq_payload") or {})
    eq_payload["fs"] = frequencies
    eq_payload["gain"] = normalized

    if new_firmware:
        body = {
            "active_eq_id": str(profile.get("active_eq_id", "0")),
            "band": int(profile.get("band") or len(frequencies)),
            "eq_payload": eq_payload,
        }
        return "setActiveEQ", body, normalized

    eq_payload.setdefault("q", [0.7070000171661377, 0.5, 0.7070000171661377])
    eq_payload.setdefault("type", [17.0, 11.0, 16.0])
    body = {
        "eq_id": str(profile.get("eq_id", "1")),
        "eq_name": profile.get("eq_name", "Custom"),
        "eq_payload": eq_payload,
        "eq_status": profile.get("eq_status", "on"),
    }
    return "setEQ", body, normalized
