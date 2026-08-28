"""
Price Resolver — product × zone × weight_tier catalog lookup.
"""

from ...data.loader import PortoDataLoader, PortoPricing
from .types import ResolvedInput


class PriceResolver:
    """Resolves price for product given ResolvedInput."""

    def __init__(self, loader: PortoDataLoader):
        self._loader = loader

    def resolve(self, input: ResolvedInput, product_id: str) -> PortoPricing | None:
        """
        Resolve price for product given ResolvedInput.
        Lookup: product_id + zone_id + weight_tier_id
        """
        return self._loader.get_price_by_product_zone_weight_tier(
            product_id,
            input.zone_id,
            input.weight_tier_id,
        )
