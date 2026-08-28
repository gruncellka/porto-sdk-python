"""
Dimension Resolver - Resolves dimensions for product.

Resolution primitive: product_id -> dimensions.
"""

from typing import Any

from ...data.loader import PortoDataLoader


class DimensionResolver:
    """Resolves dimensions for product."""

    def __init__(self, loader: PortoDataLoader):
        self._loader = loader

    def resolve(self, product_id: str) -> dict[str, Any]:
        """
        Resolve dimensions for product.
        Returns dict with is_valid, data (dimensions).
        """
        dimensions = self._loader.get_dimensions_for_product(product_id)
        return {"is_valid": True, "data": {"dimensions": dimensions}}
