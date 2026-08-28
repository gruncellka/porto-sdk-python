"""Dispatch native tracking codes to provider maps under adapters/<provider>/."""

from __future__ import annotations

from ...types import TrackingState
from ..deutschepost.tracking.status_map import DEUTSCHEPOST_SHIPMENT_STATUS_MAP
from ..laposte.tracking.status_map import LAPOSTE_STATUS_MAP
from ..swisspost.tracking.status_map import SWISSPOST_STATUS_MAP
from ..ukrposhta.tracking.status_map import UKRPOSHTA_STATUS_MAP


def map_native_status(
    provider_id: str,
    native_code: str,
) -> TrackingState | None:
    """Map a carrier-native code to SDK TrackingState."""
    code = native_code.strip()
    provider = provider_id.strip().lower()
    table = {
        "laposte": LAPOSTE_STATUS_MAP,
        "ukrposhta": UKRPOSHTA_STATUS_MAP,
        "swisspost": SWISSPOST_STATUS_MAP,
        "deutschepost": DEUTSCHEPOST_SHIPMENT_STATUS_MAP,
    }.get(provider, {})
    return table.get(code) or table.get(code.upper()) or table.get(code.lower())
