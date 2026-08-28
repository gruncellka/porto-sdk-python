"""Legal restriction applicability (provider → jurisdiction → destination)."""

from __future__ import annotations

from datetime import date
from typing import Any, Collection, cast

from porto_sdk.data.entities.restrictions import remaining_jurisdiction_map

from .types import (
    JurisdictionInstrument,
    LegalRestriction,
    RestrictionImpact,
    RestrictionJurisdiction,
)

_KNOWN: frozenset[str] = frozenset({"EU", "CH", "UA"})


def _jurisdictions_flat(
    raw: dict[str, list[dict[str, Any]]],
) -> tuple[JurisdictionInstrument, ...]:
    items: list[JurisdictionInstrument] = []
    for key, instruments in raw.items():
        jurisdiction = str(key).upper()
        if jurisdiction not in _KNOWN:
            continue
        for item in instruments:
            if not isinstance(item, dict):
                continue
            items.append(
                JurisdictionInstrument(
                    jurisdiction=cast(RestrictionJurisdiction, jurisdiction),
                    reference=(
                        item.get("reference") if isinstance(item.get("reference"), str) else None
                    ),
                    effective_from=(
                        item.get("effective_from")
                        if isinstance(item.get("effective_from"), str)
                        else None
                    ),
                    effective_to=(
                        item.get("effective_to")
                        if isinstance(item.get("effective_to"), str)
                        else None
                    ),
                )
            )
    return tuple(items)


def _item_impact(partial: bool) -> RestrictionImpact:
    return "warn" if partial else "block"


def resolve(
    catalog: dict[str, dict[str, Any]],
    country_code: str,
    region_code: str | None,
    *,
    jurisdictions: Collection[str] | None,
    today: date,
) -> list[LegalRestriction]:
    """Resolve legal matches for one destination under provider jurisdiction."""
    country = str(country_code).upper()
    region = region_code.upper() if region_code else None
    payload = catalog.get(country)
    if payload is None:
        return []

    regions = payload.get("regions") if isinstance(payload.get("regions"), dict) else {}
    out: list[LegalRestriction] = []

    if regions:
        if region and region not in regions:
            return []
        candidates = {region: regions[region]} if region else regions
        for code, row in candidates.items():
            if not isinstance(row, dict):
                continue
            raw_jurisdictions = row.get("jurisdictions")
            remaining = remaining_jurisdiction_map(
                cast(dict[str, list[dict[str, Any]]], raw_jurisdictions)
                if isinstance(raw_jurisdictions, dict)
                else {},
                provider_jurisdictions=jurisdictions,
                today=today,
            )
            if not remaining:
                continue
            partial = row.get("partial") is True
            out.append(
                LegalRestriction(
                    impact=_item_impact(partial),
                    country_code=country,
                    region_code=str(code),
                    partial=partial,
                    jurisdictions=_jurisdictions_flat(remaining),
                    reason=str(row.get("reason") or ""),
                    description=str(row.get("description") or ""),
                )
            )
        return out

    raw_jurisdictions = payload.get("jurisdictions")
    remaining = remaining_jurisdiction_map(
        cast(dict[str, list[dict[str, Any]]], raw_jurisdictions)
        if isinstance(raw_jurisdictions, dict)
        else {},
        provider_jurisdictions=jurisdictions,
        today=today,
    )
    if not remaining:
        return []
    return [
        LegalRestriction(
            impact="block",
            country_code=country,
            region_code=None,
            partial=False,
            jurisdictions=_jurisdictions_flat(remaining),
            reason=str(payload.get("reason") or ""),
            description=str(payload.get("description") or ""),
        )
    ]
