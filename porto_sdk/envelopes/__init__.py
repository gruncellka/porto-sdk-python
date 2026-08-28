"""Envelope domain package."""

from .match import EnvelopeMatchService, JsonFormatCatalog, validate_product_envelope
from .types import (
    AdvisoryMatch,
    Envelope,
    EnvelopeGeometry,
    EnvelopeLayout,
    EnvelopeMark,
    EnvelopeMarkFact,
    EnvelopeRect,
    EnvelopeSheet,
    EnvelopeSize,
    Match,
    NoMatch,
    StrictMatch,
)

__all__ = [
    "AdvisoryMatch",
    "Envelope",
    "EnvelopeGeometry",
    "EnvelopeLayout",
    "EnvelopeMark",
    "EnvelopeMarkFact",
    "EnvelopeMatchService",
    "EnvelopeRect",
    "EnvelopeSheet",
    "EnvelopeSize",
    "JsonFormatCatalog",
    "Match",
    "NoMatch",
    "StrictMatch",
    "validate_product_envelope",
]
