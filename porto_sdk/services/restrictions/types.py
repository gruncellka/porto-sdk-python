"""Public restriction result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RestrictionJurisdiction = Literal["EU", "CH", "UA"]
RestrictionImpact = Literal["block", "warn"]


@dataclass(frozen=True)
class JurisdictionInstrument:
    """In-force legal instrument under a jurisdictions.json identifier."""

    jurisdiction: RestrictionJurisdiction
    reference: str | None
    effective_from: str | None
    effective_to: str | None


@dataclass(frozen=True)
class LegalRestriction:
    impact: RestrictionImpact = "block"
    country_code: str = ""
    region_code: str | None = None
    partial: bool = False
    jurisdictions: tuple[JurisdictionInstrument, ...] = ()
    reason: str = ""
    description: str = ""


@dataclass(frozen=True)
class RoutingRestriction:
    impact: Literal["warn"] = "warn"
    country_code: str = ""
    region_code: str | None = None
    partial: bool = False
    authority: str = ""
    reference: str = ""
    reason: str = ""
    description: str = ""


@dataclass(frozen=True)
class Restrictions:
    """Resolved destination restriction result (not a catalog dump)."""

    impact: RestrictionImpact | None
    legal: tuple[LegalRestriction, ...] = field(default_factory=tuple)
    routing: tuple[RoutingRestriction, ...] = field(default_factory=tuple)
