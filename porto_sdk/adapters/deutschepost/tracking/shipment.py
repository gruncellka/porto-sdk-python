"""Deutsche Post shipment tracking (Sendungsverfolgung wire). Not Internetmarke."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from ....errors import PortoError, PortoErrorCode
from ....provider_payload import sanitize_provider_payload
from ....types import TrackingStatus
from ...tracking.adapter import TrackingAdapter, assemble_tracking, map_event


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class Adapter(TrackingAdapter):
    """Live poll against an explicit shipment base URL. Empty URL never selects this class."""

    def __init__(self, *, base_url: str, http_client: object | None) -> None:
        self.provider_id = "deutschepost"
        self.tracking_kind = "shipment"
        self.supports_tracking = True
        self.wire = "shipment"
        self._base_url = base_url.rstrip("/")
        self._http = http_client

    async def track(self, tracking_number: str) -> TrackingStatus:
        if self._http is None or not hasattr(self._http, "request"):
            raise PortoError(
                "Shipment tracking HTTP client is not configured.",
                PortoErrorCode.PORTO_NETWORK_UNAVAILABLE,
                status_code=503,
                provider=self.provider_id,
                wire=self.wire,
                retryable=False,
            )
        url = f"{self._base_url}/{quote(tracking_number, safe='')}"
        response = await self._http.request(
            method="GET",
            url=url,
            headers={"Accept": "application/json"},
        )
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code == 404:
            raise PortoError(
                "Tracking number was not found.",
                PortoErrorCode.PORTO_TRACKING_NOT_FOUND,
                status_code=404,
                provider=self.provider_id,
                wire=self.wire,
                details={"tracking_number": tracking_number},
                retryable=False,
            )
        if status_code >= 400:
            raise PortoError(
                "Shipment tracking request failed.",
                PortoErrorCode.PORTO_NETWORK_UNAVAILABLE,
                status_code=status_code or 502,
                provider=self.provider_id,
                wire=self.wire,
                retryable=status_code >= 500,
            )
        payload = response.json() if hasattr(response, "json") else {}
        if not isinstance(payload, dict):
            raise PortoError(
                "Shipment tracking returned an unexpected payload.",
                PortoErrorCode.PORTO_NETWORK_UNAVAILABLE,
                status_code=502,
                provider=self.provider_id,
                wire=self.wire,
                retryable=False,
            )
        return snapshot(
            tracking_number=tracking_number,
            payload=payload,
        )


def snapshot(*, tracking_number: str, payload: dict[str, Any]) -> TrackingStatus:
    raw_events = payload.get("events")
    rows = list(raw_events) if isinstance(raw_events, list) else []
    current = payload.get("currentEvent")
    if isinstance(current, dict):
        rows.append(current)
    received_at = _iso_now()
    history = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        code = str(row.get("historicalState") or row.get("state") or row.get("code") or "").strip()
        if not code:
            continue
        # occurredAt/occurred_at are compatibility fixture aliases, not DP wire fields.
        event = map_event(
            provider_id="deutschepost",
            tracking_number=tracking_number,
            native_code=code,
            native_label=_optional_str(
                row.get("shortStatus") or row.get("status") or row.get("label")
            ),
            occurred_at=row.get("timestamp") or row.get("occurredAt") or row.get("occurred_at"),
            received_at=received_at,
            native_id=row.get("eventId") or row.get("id"),
            native_sequence=row.get("sequence") or row.get("step"),
            native_index=index,
            location=_optional_str(row.get("location")),
            description=_optional_str(row.get("status") or row.get("description")),
        )
        if event.event_id not in seen:
            seen.add(event.event_id)
            history.append(event)
    assembled = assemble_tracking(history)
    sanitized = sanitize_provider_payload(payload)
    return TrackingStatus(
        tracking_number=tracking_number,
        provider_id="deutschepost",
        tracking_kind="shipment",
        status=assembled.status,
        last_update=assembled.last_update,
        status_changed_at=assembled.status_changed_at,
        poll_received_at=received_at,
        location=assembled.location,
        history=history,
        provider_raw=sanitized if isinstance(sanitized, dict) else None,
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
