"""La Poste Suivi — placeholder map for future live wire."""

from ....types import TrackingState

LAPOSTE_STATUS_MAP: dict[str, TrackingState] = {
    "PC1": TrackingState.CREATED,
    "PC2": TrackingState.IN_TRANSIT,
    "PC3": TrackingState.OUT_FOR_DELIVERY,
    "LIV": TrackingState.DELIVERED,
    "REN": TrackingState.RETURNED,
    "NDR": TrackingState.UNDELIVERABLE,
}
