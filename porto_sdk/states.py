"""Capability and availability states — not boolean collapse."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CapabilityState(str, Enum):
    """Distinct runtime outcomes for an optional SDK capability."""

    ABSENT = "absent"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    READY = "ready"

    def __bool__(self) -> bool:
        return self is CapabilityState.READY


def capability_state(*, supported: bool, available: bool = True) -> CapabilityState:
    if not supported:
        return CapabilityState.UNSUPPORTED
    if not available:
        return CapabilityState.UNAVAILABLE
    return CapabilityState.READY


@dataclass(frozen=True)
class HealthStatus:
    state: CapabilityState
    detail: str | None = None
