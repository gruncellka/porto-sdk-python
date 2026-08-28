"""Aggregate machine impact from resolved restriction leaves."""

from __future__ import annotations

from .types import LegalRestriction, RestrictionImpact, RoutingRestriction


def resolve(
    legal: list[LegalRestriction],
    routing: list[RoutingRestriction],
    *,
    region_precise: bool,
) -> RestrictionImpact | None:
    """Top-level impact from matched legal + routing leaves.

    Country-only (region not precise) always yields ``warn`` when any leaf
    matches, even if some legal leaves would ``block`` when selected alone.
    """
    if not legal and not routing:
        return None
    if not region_precise:
        return "warn"
    if any(item.impact == "block" for item in legal):
        return "block"
    return "warn"
