"""
Weight Tier Resolver - Resolves weight_tier_id from weight in grams.

Uses lookup_rules.weight_resolution: find tier where min <= weight <= max.
"""

from ...data.loader import PortoDataLoader


class WeightTierResolver:
    """Resolves weight tier ID for a given weight."""

    def __init__(self, loader: PortoDataLoader):
        self._loader = loader

    def resolve(self, weight: int) -> str | None:
        """
        Resolve weight tier for given weight.
        Finds weight_tier where min <= weight <= max.
        """
        weight_tiers = self._loader.get_all_weight_tiers()
        sorted_tiers = sorted(weight_tiers, key=lambda t: t.max_weight)

        for i, tier in enumerate(sorted_tiers):
            min_weight = 0
            if i > 0:
                min_weight = sorted_tiers[i - 1].max_weight + 1
            if min_weight <= weight <= tier.max_weight:
                return tier.id

        return None
