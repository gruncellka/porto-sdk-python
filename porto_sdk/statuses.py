# GENERATED from porto_features/statuses.json — do not edit.
# Run: make sync-bindings

from enum import Enum


class PortoStatus(str, Enum):
    """Normalized carrier status. Not mark existence, and not an unknown bucket."""

    CREATED = "created"
    TRANSIT = "transit"
    DELIVERY = "delivery"
    DELIVERED = "delivered"
    RETURNED = "returned"
    UNDELIVERABLE = "undeliverable"
