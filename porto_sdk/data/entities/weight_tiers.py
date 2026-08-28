"""
Weight Tiers Entity Loader

Handles loading and querying weight tiers entity.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import BaseEntityLoader


@dataclass
class PortoWeightTier:
    """
    Weight tier model - maps to porto-data/schemas/weight_tiers.schema.json

    JSON structure:
    {
        "id": "W0020",  # pattern: ^W[0-9]+$
        "max_weight": 20  # grams
    }
    """

    id: str
    max_weight: int  # grams


class WeightTiersLoader(BaseEntityLoader):
    """
    Loads and manages weight tiers entity

    Handles:
    - Loading weight tiers from JSON (dict format where keys are tier IDs)
    - Querying weight tiers by ID
    """

    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._weight_tiers: list[PortoWeightTier] = []

    def load(self, data: dict[str, Any]) -> None:
        """
        Transform weight tiers JSON to PortoWeightTier objects

        Weight tiers is a dict where keys are tier IDs, values are tier data.
        """
        weight_tiers_data = data.get("weight_tiers", {})
        self._weight_tiers = [
            PortoWeightTier(id=tier_id, max_weight=tier_data.get("max", 0))
            for tier_id, tier_data in weight_tiers_data.items()
        ]

    def get_data(self) -> list[PortoWeightTier]:
        """Get all weight tiers"""
        return self._weight_tiers

    # Query methods specific to weight tiers
    def get_weight_tier(self, tier_id: str) -> PortoWeightTier | None:
        """Get weight tier by ID"""
        return next((wt for wt in self._weight_tiers if wt.id == tier_id), None)

    def get_all_weight_tiers(self) -> list[PortoWeightTier]:
        """Get all weight tiers"""
        return self._weight_tiers
