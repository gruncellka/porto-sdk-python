"""Routing restriction applicability (destination geography only)."""

from __future__ import annotations

from typing import Any

from .types import RoutingRestriction


def resolve(
    catalog: dict[str, dict[str, Any]],
    country_code: str,
    region_code: str | None,
) -> list[RoutingRestriction]:
    """Resolve routing matches for one destination (no provider jurisdiction)."""
    country = str(country_code).upper()
    region = region_code.upper() if region_code else None
    payload = catalog.get(country)
    if payload is None:
        return []

    authority = str(payload.get("authority") or "")
    reference = str(payload.get("reference") or "")
    reason = str(payload.get("reason") or "")
    description = str(payload.get("description") or "")
    regions = payload.get("regions") if isinstance(payload.get("regions"), dict) else {}

    if not regions:
        return [
            RoutingRestriction(
                country_code=country,
                region_code=None,
                partial=False,
                authority=authority,
                reference=reference,
                reason=reason,
                description=description,
            )
        ]

    if region:
        if region not in regions:
            return []
        row = regions[region] if isinstance(regions[region], dict) else {}
        return [
            RoutingRestriction(
                country_code=country,
                region_code=region,
                partial=row.get("partial") is True,
                authority=authority,
                reference=reference,
                reason=reason,
                description=description,
            )
        ]

    out: list[RoutingRestriction] = []
    for code, row in regions.items():
        payload_row = row if isinstance(row, dict) else {}
        out.append(
            RoutingRestriction(
                country_code=country,
                region_code=str(code),
                partial=payload_row.get("partial") is True,
                authority=authority,
                reference=reference,
                reason=reason,
                description=description,
            )
        )
    return out
