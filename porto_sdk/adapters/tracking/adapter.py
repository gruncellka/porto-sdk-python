"""Tracking adapter protocol and provider-bound implementations."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Literal

from ...errors import PortoError, PortoErrorCode
from ...types import TrackingEvent, TrackingState, TrackingStatus
from .acl import map_native_status

TrackingKind = Literal["shipment", "stamp"]


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def build_event_id(
    provider_id: str,
    tracking_number: str,
    provider_code: str,
    occurred_at: str,
) -> str:
    raw = f"{provider_id}:{tracking_number}:{provider_code}:{occurred_at}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class TrackingAdapter(ABC):
    provider_id: str
    supports_tracking: bool
    tracking_kind: TrackingKind

    @abstractmethod
    async def track(self, tracking_number: str) -> TrackingStatus:
        raise NotImplementedError


class UnsupportedTrackingAdapter(TrackingAdapter):
    """Explicit unsupported tracking for a provider wire (e.g. Internetmarke stamp)."""

    def __init__(
        self,
        provider_id: str,
        *,
        wire: str = "none",
        tracking_kind: TrackingKind = "stamp",
        reason: str | None = None,
    ) -> None:
        self.provider_id = provider_id.strip().lower()
        self.wire = wire
        self.tracking_kind: TrackingKind = tracking_kind
        self.supports_tracking = False
        self._reason = reason or "Tracking is not supported for this provider wire."

    async def track(self, tracking_number: str) -> TrackingStatus:
        raise PortoError(
            self._reason,
            PortoErrorCode.PORTO_TRACKING_UNSUPPORTED,
            status_code=501,
            provider=self.provider_id,
            wire=self.wire,
            details={
                "provider_id": self.provider_id,
                "wire": self.wire,
                "tracking_kind": self.tracking_kind,
                "tracking_number": tracking_number,
            },
            retryable=False,
        )


class StubTrackingAdapter(TrackingAdapter):
    """Stub adapter with ACL maps — supports_tracking=false until live HTTP ships."""

    def __init__(self, provider_id: str, *, tracking_kind: TrackingKind = "shipment") -> None:
        self.provider_id = provider_id.strip().lower()
        self.tracking_kind = tracking_kind
        self.supports_tracking = False

    async def track(self, tracking_number: str) -> TrackingStatus:
        raise PortoError(
            f"Live tracking is not yet wired for {self.provider_id}.",
            PortoErrorCode.PORTO_TRACKING_UNSUPPORTED,
            status_code=501,
            provider=self.provider_id,
            details={
                "provider_id": self.provider_id,
                "tracking_kind": self.tracking_kind,
                "tracking_number": tracking_number,
            },
            retryable=False,
        )


def map_event(
    *,
    provider_id: str,
    tracking_number: str,
    native_code: str,
    native_label: str | None,
    occurred_at: str,
    received_at: str,
    location: str | None = None,
    description: str | None = None,
) -> TrackingEvent:
    status = map_native_status(provider_id, native_code)
    if status is None:
        status = TrackingState.IN_TRANSIT
    event_id = build_event_id(provider_id, tracking_number, native_code, occurred_at)
    return TrackingEvent(
        event_id=event_id,
        provider_id=provider_id,
        provider_code=native_code,
        provider_label=native_label,
        occurred_at=occurred_at,
        received_at=received_at,
        status=status,
        location=location,
        description=description,
    )


def get_tracking_adapter(
    provider_id: str,
    *,
    wire_id: str | None = None,
    data_path: str | None = None,
) -> TrackingAdapter:
    """Resolve tracking adapter for a bound provider execution context."""
    provider = provider_id.strip().lower()
    wire = (wire_id or "").strip().lower()

    if provider == "deutschepost" and wire == "internetmarke":
        return UnsupportedTrackingAdapter(
            provider,
            wire="internetmarke",
            tracking_kind="stamp",
            reason=(
                "Internetmarke stamp marks do not support shipment tracking. "
                "Use a Sendungsverfolgung wire when available."
            ),
        )

    return StubTrackingAdapter(provider, tracking_kind="shipment")
