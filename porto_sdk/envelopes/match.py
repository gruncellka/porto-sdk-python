"""Envelope catalog and matching policy."""

from __future__ import annotations

from typing import Protocol

from ..data.entities.envelopes import EnvelopesLoader, PortoEnvelope
from ..data.entities.products import PortoProduct
from .types import (
    ADVISORY_TOLERANCE_MM,
    AdvisoryMatch,
    Match,
    NoMatch,
    StrictMatch,
)


class IFormatCatalog(Protocol):
    def get_envelope(self, envelope_id: str) -> PortoEnvelope | None: ...

    def list_envelopes(self) -> list[PortoEnvelope]: ...

    def all_ids(self) -> set[str]: ...


class JsonFormatCatalog:
    def __init__(self, loader: EnvelopesLoader):
        self._loader = loader

    def get_envelope(self, envelope_id: str) -> PortoEnvelope | None:
        return self._loader.get_envelope(envelope_id)

    def list_envelopes(self) -> list[PortoEnvelope]:
        return self._loader.list_envelopes()

    def all_ids(self) -> set[str]:
        return self._loader.all_ids()


def validate_product_envelope(product: PortoProduct, envelope_id: str) -> bool:
    return envelope_id in (product.envelope_ids or [])


def _normalize_dims(width: int, height: int) -> tuple[int, int]:
    return (max(width, height), min(width, height))


def chebyshev_distance(a: PortoEnvelope, b: PortoEnvelope) -> float:
    long_a, short_a = _normalize_dims(a.width, a.height)
    long_b, short_b = _normalize_dims(b.width, b.height)
    return float(max(abs(long_a - long_b), abs(short_a - short_b)))


class EnvelopeMatchService:
    def __init__(self, catalog: IFormatCatalog):
        self._catalog = catalog

    def resolve_by_id(self, envelope_id: str, product: PortoProduct) -> Match:
        envelope = self._catalog.get_envelope(envelope_id)
        if envelope is None:
            return NoMatch(reason="unknown_envelope")

        if validate_product_envelope(product, envelope_id):
            return StrictMatch(envelope_id=envelope_id)

        allowed = [
            self._catalog.get_envelope(eid)
            for eid in product.envelope_ids
            if self._catalog.get_envelope(eid) is not None
        ]
        allowed = [e for e in allowed if e is not None]
        if not allowed:
            return NoMatch(reason="not_in_product_list")

        closest = min(allowed, key=lambda candidate: chebyshev_distance(envelope, candidate))  # type: ignore[arg-type]
        score = chebyshev_distance(envelope, closest)  # type: ignore[arg-type]
        reason = "dimensions_close" if score <= ADVISORY_TOLERANCE_MM else "regional_format"
        return AdvisoryMatch(
            envelope_id=envelope_id,
            closest_allowed_id=closest.id,  # type: ignore[union-attr]
            score=score,
            reason=reason,  # type: ignore[arg-type]
            tolerance_mm=ADVISORY_TOLERANCE_MM,
        )

    def resolve_by_dimensions(self, width_mm: int, height_mm: int, product: PortoProduct) -> Match:
        long_edge, short_edge = _normalize_dims(width_mm, height_mm)
        exact = [
            e
            for e in self._catalog.list_envelopes()
            if _normalize_dims(e.width, e.height) == (long_edge, short_edge)
        ]
        if len(exact) == 1:
            return self.resolve_by_id(exact[0].id, product)
        if len(exact) > 1:
            return NoMatch(reason="ambiguous_dimensions")
        return NoMatch(reason="unknown_envelope")
