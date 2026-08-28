"""
Resolution types — shared across resolution primitives.

Catalog identity is concrete ``id``. Service/feature ``kind`` is grouping only.
"""

from dataclasses import dataclass
from typing import Literal

DeliveryPreference = Literal["fastest", "cheapest", "economy"]


@dataclass
class ResolvedInput:
    """Inputs shared by ProductResolver / PriceResolver helpers."""

    zone_id: str
    weight_tier_id: str
    product_id: str | None = None
    envelope_id: str | None = None
    delivery_preference: DeliveryPreference | None = None
    indemnity_tier: str | None = None


@dataclass(frozen=True)
class DestinationCountry:
    """Supported destination country from porto-data zones (ISO 3166-1 alpha-2)."""

    code: str
    zone_id: str
