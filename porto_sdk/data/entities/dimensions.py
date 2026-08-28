"""
Dimensions Entity Loader

Handles loading and querying dimensions entity.
"""

from pathlib import Path
from typing import Any

from .base import BaseEntityLoader


class DimensionsLoader(BaseEntityLoader):
    """
    Loads and manages dimensions entity

    Handles:
    - Loading dimensions from JSON
    - Querying dimensions by ID or for a product
    """

    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._dimensions: list[dict[str, Any]] = []

    def load(self, data: dict[str, Any]) -> None:
        """Transform dimensions JSON to dimension objects"""
        self._dimensions = data.get("dimensions", [])

    def get_data(self) -> list[dict[str, Any]]:
        """Get all dimensions"""
        return self._dimensions

    # Query methods specific to dimensions
    def get_dimension(self, dimension_id: str) -> dict[str, Any] | None:
        """Get dimension by ID"""
        return next((d for d in self._dimensions if d.get("id") == dimension_id), None)

    def get_dimensions_for_product(
        self, product_id: str, product_envelope_ids: list[str]
    ) -> list[dict[str, Any]]:
        """
        Get dimensions for a product based on product's envelope_ids

        Args:
            product_id: Product ID (for logging/debugging)
            product_envelope_ids: List of dimension IDs from product

        Returns:
            List of dimension objects matching product's envelope_ids
        """
        return [d for d in self._dimensions if d.get("id") in product_envelope_ids]

    def get_all_dimensions(self) -> list[dict[str, Any]]:
        """Get all dimensions"""
        return self._dimensions
