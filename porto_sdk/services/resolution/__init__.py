"""
Resolution primitives — shared building blocks for ``PortoResolver.resolve``.

Catalog identity is concrete ``id``. Service/feature ``kind`` is grouping only.
"""

from .cache import ResolutionCache
from .delivery_resolver import DeliveryHint, DeliveryResolver, WorkingDaysHint
from .dimension_resolver import DimensionResolver
from .feature_resolver import FeatureResolver
from .fingerprint import resolution_fingerprint
from .price_resolver import PriceResolver
from .product_resolver import ProductResolver
from .quote import ComposedQuote, PriceComponent, compose_quote
from .service_resolver import (
    ServiceResolver,
    bind_requested_services,
    resolve_service_token,
    validate_service_selection,
)
from .types import (
    DeliveryPreference,
    DestinationCountry,
    ResolvedInput,
)
from .weight_tier_resolver import WeightTierResolver
from .zone_resolver import ZoneResolver

__all__ = [
    "DeliveryHint",
    "DeliveryPreference",
    "DeliveryResolver",
    "DestinationCountry",
    "DimensionResolver",
    "FeatureResolver",
    "PriceResolver",
    "ComposedQuote",
    "PriceComponent",
    "compose_quote",
    "ProductResolver",
    "ResolutionCache",
    "ResolvedInput",
    "bind_requested_services",
    "resolve_service_token",
    "validate_service_selection",
    "ServiceResolver",
    "WeightTierResolver",
    "WorkingDaysHint",
    "ZoneResolver",
    "resolution_fingerprint",
]
