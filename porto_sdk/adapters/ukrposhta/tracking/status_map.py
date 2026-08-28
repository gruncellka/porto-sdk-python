"""Ukrposhta — placeholder map for future live wire."""

from ....types import TrackingState

UKRPOSHTA_STATUS_MAP: dict[str, TrackingState] = {
    "101": TrackingState.CREATED,
    "102": TrackingState.IN_TRANSIT,
    "103": TrackingState.OUT_FOR_DELIVERY,
    "104": TrackingState.DELIVERED,
    "105": TrackingState.RETURNED,
    "106": TrackingState.UNDELIVERABLE,
}
