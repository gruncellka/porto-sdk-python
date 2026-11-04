"""Tracking adapter protocol and provider-bound implementations."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Literal, NamedTuple

from ...errors import PortoError, PortoErrorCode
from ...types import PortoStatus, TrackingEvent, TrackingStatus
from .acl import map_native_status
from .time import normalize_occurred_at

TrackingKind = Literal["letter", "stamp"]


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def build_event_id(
    provider_id: str,
    tracking_number: str,
    provider_code: str,
    *,
    native_id: object | None = None,
    native_sequence: object | None = None,
    native_index: int | None = None,
    occurred_at: str | None = None,
) -> str:
    if native_id is not None and str(native_id).strip():
        discriminator = f"id:{str(native_id).strip()}"
    elif native_sequence is not None and str(native_sequence).strip():
        discriminator = f"sequence:{str(native_sequence).strip()}"
    elif native_index is not None:
        discriminator = f"index:{native_index}:time:{occurred_at or ''}"
    else:
        discriminator = f"time:{occurred_at or ''}"
    raw = f"{provider_id}:{tracking_number}:{provider_code}:{discriminator}"
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

    def __init__(self, provider_id: str, *, tracking_kind: TrackingKind = "letter") -> None:
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
    occurred_at: object | None,
    received_at: str,
    native_id: object | None = None,
    native_sequence: object | None = None,
    native_index: int | None = None,
    location: str | None = None,
    description: str | None = None,
) -> TrackingEvent:
    status = map_native_status(provider_id, native_code)
    occurred = normalize_occurred_at(occurred_at)
    event_id = build_event_id(
        provider_id,
        tracking_number,
        native_code,
        native_id=native_id,
        native_sequence=native_sequence,
        native_index=native_index,
        occurred_at=occurred.value if occurred else None,
    )
    return TrackingEvent(
        event_id=event_id,
        provider_id=provider_id,
        provider_code=native_code,
        provider_label=native_label,
        occurred_at=occurred.value if occurred else None,
        occurred_kind=occurred.kind if occurred else None,
        received_at=received_at,
        status=status,
        location=location,
        description=description,
    )


class TrackingAssembly(NamedTuple):
    status: PortoStatus | None
    last_update: str | None
    status_changed_at: str | None
    location: str | None


def assemble_tracking(history: list[TrackingEvent]) -> TrackingAssembly:
    """Derive a snapshot from events already arranged in provider chronology."""
    latest = history[-1] if history else None
    mapped = [event for event in history if event.status is not None]
    current = mapped[-1] if mapped else None
    changed = current
    if current is not None:
        for event in reversed(mapped[:-1]):
            if event.status != current.status:
                break
            changed = event
    return TrackingAssembly(
        status=current.status if current else None,
        last_update=latest.occurred_at if latest else None,
        status_changed_at=changed.occurred_at if changed else None,
        location=latest.location if latest else None,
    )


# Provider wire key (Deutsche Post Sendungsverfolgung). Not the public tracking kind.
SHIPMENT_WIRE_ID = "shipment"


def tracking_wire_id(wires: object | None) -> str | None:
    """Explicit shipment wire only. Missing or blank config is not a live alias."""
    if not isinstance(wires, dict) or SHIPMENT_WIRE_ID not in wires:
        return None
    wire = wires[SHIPMENT_WIRE_ID]
    base = str(getattr(wire, "base_url", None) or "").strip()
    if not base:
        return None
    return SHIPMENT_WIRE_ID


def get_tracking_adapter(
    provider_id: str,
    *,
    wire_id: str | None = None,
    data_path: str | None = None,
    base_url: str | None = None,
    http_client: object | None = None,
) -> TrackingAdapter:
    """Resolve a tracking adapter from an explicit tracking wire, not the execution wire."""
    del data_path
    provider = provider_id.strip().lower()
    wire = (wire_id or "").strip().lower()

    if not wire:
        return UnsupportedTrackingAdapter(
            provider,
            wire="none",
            tracking_kind="letter",
            reason="No tracking wire is configured.",
        )

    if provider == "deutschepost" and wire == "internetmarke":
        return UnsupportedTrackingAdapter(
            provider,
            wire="internetmarke",
            tracking_kind="stamp",
            reason=(
                "Internetmarke stamp marks do not support letter tracking. "
                "Use a Sendungsverfolgung wire when available."
            ),
        )

    if provider == "deutschepost" and wire == SHIPMENT_WIRE_ID:
        base = (base_url or "").strip()
        if not base:
            return UnsupportedTrackingAdapter(
                provider,
                wire=SHIPMENT_WIRE_ID,
                tracking_kind="letter",
                reason="Letter tracking requires an explicit base URL.",
            )
        from ..deutschepost.tracking.shipment import Adapter as Shipment

        return Shipment(
            base_url=base,
            http_client=http_client,
        )

    return StubTrackingAdapter(provider, tracking_kind="letter")
