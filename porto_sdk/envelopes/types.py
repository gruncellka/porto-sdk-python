"""Envelope matching types — PUBLIC_API structured Match."""

from dataclasses import dataclass, fields
from typing import Any, Literal, Union

AdvisoryReason = Literal[
    "dimensions_close",
    "regional_format",
    "unlisted_supply",
    "ambiguous_dimensions",
]

NoMatchReason = Literal[
    "not_in_product_list",
    "beyond_tolerance",
    "unknown_envelope",
    "ambiguous_dimensions",
]


class OmitNone:
    """Dict-like access that treats None as omitted (absence, not null)."""

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        names = {item.name for item in fields(self)}  # type: ignore[arg-type]
        if key not in names:
            return False
        return getattr(self, key) is not None

    def __getitem__(self, key: str) -> Any:
        if key not in self:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        if key not in self:
            return default
        return getattr(self, key)

    def __eq__(self, other: object) -> bool:
        names = [item.name for item in fields(self)]  # type: ignore[arg-type]
        if isinstance(other, dict):
            data = {name: getattr(self, name) for name in names if getattr(self, name) is not None}
            return data == other
        if isinstance(other, type(self)):
            return all(getattr(self, name) == getattr(other, name) for name in names)
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]


@dataclass(frozen=True, eq=False)
class EnvelopeSheet(OmitNone):
    sheet: str
    fold: str
    description: str | None = None


@dataclass(frozen=True, eq=False)
class EnvelopeRect(OmitNone):
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, eq=False)
class EnvelopeSize(OmitNone):
    width: float
    height: float


@dataclass(frozen=True, eq=False)
class Envelope(OmitNone):
    id: str
    name: str
    width: int
    height: int
    sheets: tuple[EnvelopeSheet, ...] = ()


@dataclass(frozen=True, eq=False)
class EnvelopeGeometry(OmitNone):
    id: str
    name: str
    width: int
    height: int
    sheets: tuple[EnvelopeSheet, ...] = ()
    window: EnvelopeRect | None = None
    notes: str | None = None


@dataclass(frozen=True, eq=False)
class EnvelopeMarkFact(OmitNone):
    type: str
    size: EnvelopeSize
    profile_id: str
    clearance: float | None = None
    placement: EnvelopeRect | None = None


@dataclass(frozen=True, eq=False)
class EnvelopeLayout(OmitNone):
    envelope_id: str
    width: int
    height: int
    window: EnvelopeRect | None = None
    mark: EnvelopeMarkFact | None = None


@dataclass(frozen=True, eq=False)
class EnvelopeMark(OmitNone):
    provider_id: str
    profile_id: str
    type: str
    size: EnvelopeSize
    product_id: str | None = None
    zone_id: str | None = None
    clearance: float | None = None
    placement: EnvelopeRect | None = None


@dataclass(frozen=True)
class StrictMatch:
    kind: Literal["strict_match"] = "strict_match"
    envelope_id: str = ""
    advisory_only: bool = False


@dataclass(frozen=True)
class AdvisoryMatch:
    kind: Literal["advisory_match"] = "advisory_match"
    envelope_id: str = ""
    closest_allowed_id: str = ""
    score: float = 0.0
    advisory_only: bool = True
    reason: AdvisoryReason = "dimensions_close"
    tolerance_mm: float | None = None


@dataclass(frozen=True)
class NoMatch:
    kind: Literal["no_match"] = "no_match"
    reason: NoMatchReason | None = None


Match = Union[StrictMatch, AdvisoryMatch, NoMatch]

EnvelopeCandidateById = dict  # {"kind": "by_id", "envelope_id": str}
EnvelopeCandidateByDimensions = dict  # {"kind": "by_dimensions", "width": int, "height": int}

ADVISORY_TOLERANCE_MM = 15.0
