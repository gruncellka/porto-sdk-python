"""Dispatch native tracking codes to provider maps under adapters/<provider>/."""

from __future__ import annotations

from collections.abc import Mapping

from ...types import PortoStatus
from ..deutschepost.tracking.status_map import MAP as deutschepost
from ..laposte.tracking.status_map import MAP as laposte
from ..swisspost.tracking.status_map import MAP as swisspost
from ..ukrposhta.tracking.status_map import MAP as ukrposhta

STATUS_MAPS: Mapping[str, Mapping[str, PortoStatus]] = {
    "deutschepost": deutschepost,
    "laposte": laposte,
    "swisspost": swisspost,
    "ukrposhta": ukrposhta,
}


def map_native_status(
    provider_id: str,
    native_code: str,
) -> PortoStatus | None:
    """Map a carrier-native code to PortoStatus. Unknown codes stay unmapped."""
    code = native_code.strip()
    table = STATUS_MAPS.get(provider_id.strip().lower(), {})
    return table.get(code) or table.get(code.upper()) or table.get(code.lower())
