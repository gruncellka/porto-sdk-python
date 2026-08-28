"""Provider-scoped tracking service."""

from __future__ import annotations

from ..adapters.tracking.adapter import TrackingAdapter
from ..errors import PortoError, PortoErrorCode
from ..types import TrackingStatus


class TrackingService:
    def __init__(self, adapter: TrackingAdapter) -> None:
        self._adapter = adapter

    @property
    def supports_tracking(self) -> bool:
        return self._adapter.supports_tracking

    async def get(self, tracking_number: str) -> TrackingStatus:
        number = str(tracking_number).strip()
        if not number:
            raise PortoError(
                "Tracking number is required.",
                PortoErrorCode.PORTO_TRACKING_NOT_FOUND,
                status_code=404,
                provider=self._adapter.provider_id,
                details={
                    "provider_id": self._adapter.provider_id,
                    "tracking_number": number,
                },
                retryable=False,
            )
        return await self._adapter.track(number)
