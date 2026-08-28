"""Swiss Post — placeholder map for future live wire."""

from ....types import TrackingState

SWISSPOST_STATUS_MAP: dict[str, TrackingState] = {
    "NOT_YET_SENT": TrackingState.CREATED,
    "ON_THE_WAY": TrackingState.IN_TRANSIT,
    "OUT_FOR_DELIVERY": TrackingState.OUT_FOR_DELIVERY,
    "DELIVERED": TrackingState.DELIVERED,
    "RETURNED": TrackingState.RETURNED,
    "NOT_DELIVERED": TrackingState.UNDELIVERABLE,
}
