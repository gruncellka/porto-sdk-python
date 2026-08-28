"""Deutsche Post Sendungsverfolgung — separate from Internetmarke stamp wire."""

from ....types import TrackingState

DEUTSCHEPOST_SHIPMENT_STATUS_MAP: dict[str, TrackingState] = {
    "pre-transit": TrackingState.CREATED,
    "transit": TrackingState.IN_TRANSIT,
    "out-for-delivery": TrackingState.OUT_FOR_DELIVERY,
    "delivered": TrackingState.DELIVERED,
    "return": TrackingState.RETURNED,
    "failure": TrackingState.UNDELIVERABLE,
}
