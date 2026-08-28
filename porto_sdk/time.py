"""Canonical SDK time encodings.

Configuration durations are seconds, stored as ``timedelta``. Convert to
float seconds or milliseconds only at httpx, sleep, or clock boundaries.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TypeAlias

DurationInput: TypeAlias = timedelta | int | float


def parse_duration(value: DurationInput) -> timedelta:
    """Parse a seconds number or timedelta into a non-negative timedelta."""
    if isinstance(value, timedelta):
        duration = value
    elif isinstance(value, (int, float)):
        duration = timedelta(seconds=float(value))
    else:
        raise TypeError(f"duration must be seconds or timedelta, got {type(value).__name__}")
    if duration.total_seconds() < 0:
        raise ValueError("duration must not be negative")
    return duration


def as_seconds(value: timedelta) -> float:
    """Convert timedelta to seconds for httpx / sleep / monotonic compare."""
    return value.total_seconds()


def as_milliseconds(value: timedelta) -> int:
    """Convert timedelta to integer milliseconds for timer APIs."""
    return int(value.total_seconds() * 1000)


def utc_now() -> datetime:
    """Timezone-aware UTC now for token expiry and cache timestamps."""
    return datetime.now(UTC)
