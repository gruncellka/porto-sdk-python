"""Dispatch native tracking codes to provider maps under adapters/<provider>/."""

from __future__ import annotations

from ...types import PortoStatus
from ..deutschepost.tracking.status_map import MAP as deutschepost
from ..laposte.tracking.status_map import MAP as laposte
from ..swisspost.tracking.status_map import MAP as swisspost
from ..ukrposhta.tracking.status_map import MAP as ukrposhta


def map_native_status(
    provider_id: str,
    native_code: str,
) -> PortoStatus | None:
    """Map a carrier-native code to PortoStatus. Unknown codes stay unmapped."""
    code = native_code.strip()
    provider = provider_id.strip().lower()
    table = {
        "laposte": laposte,
        "ukrposhta": ukrposhta,
        "swisspost": swisspost,
        "deutschepost": deutschepost,
    }.get(provider, {})
    return table.get(code) or table.get(code.upper()) or table.get(code.lower())
