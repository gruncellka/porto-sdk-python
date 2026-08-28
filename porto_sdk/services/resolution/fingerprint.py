"""Resolution fingerprint — mirrors porto-data CI delivery validator."""

from __future__ import annotations

from typing import Any

from ...data.entities.products import PortoProduct


def delivery_zone_signature(product: PortoProduct, zone_id: str) -> tuple[Any, ...] | None:
    for entry in product.delivery:
        if zone_id in entry.zones:
            return (entry.span, entry.days_min, entry.days_max, entry.weekdays)
    return None


def resolution_fingerprint(product: PortoProduct, zone_id: str) -> tuple[Any, ...]:
    tier: str | None = None
    if product.indemnity:
        tier = product.indemnity.tier
    features_key: frozenset[str] = frozenset(product.included_features or [])
    return (
        delivery_zone_signature(product, zone_id),
        tier,
        features_key,
        product.tracking,
    )
