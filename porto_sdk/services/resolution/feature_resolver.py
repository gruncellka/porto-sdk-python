"""
Feature Resolver - Resolves features for product and zone.

Resolution primitive: product_id + zone_id -> features.
"""

from typing import Any

from ...data.loader import PortoDataLoader


class FeatureResolver:
    """Resolves features for product and zone."""

    def __init__(self, loader: PortoDataLoader):
        self._loader = loader

    def resolve(self, product_id: str, zone_id: str) -> dict[str, Any]:
        """
        Resolve features for product and zone.
        Returns dict with is_valid, data (features).
        """
        features = self._loader.get_features_for_product(product_id)
        zone_features = self._loader.get_features_for_zone(zone_id)
        all_features: list[Any] = list(features) + list(zone_features)
        return {"is_valid": True, "data": {"features": all_features}}
