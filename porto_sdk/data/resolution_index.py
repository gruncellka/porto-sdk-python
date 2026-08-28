"""Graph-indexed product lookup — (zone_id, weight_tier_id) → product ids."""

from __future__ import annotations

from dataclasses import dataclass, field

from .entities.products import PortoProduct


@dataclass
class ResolutionIndex:
    """O(1) candidate lookup by (zone, weight_tier)."""

    _by_edge: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    _graph_product_ids: set[str] = field(default_factory=set)
    _tiers_by_zone: dict[str, set[str]] = field(default_factory=dict)
    _product_edges: dict[str, set[tuple[str, str]]] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        links: dict[str, dict[str, list[str]]],
        products: list[PortoProduct],
    ) -> ResolutionIndex:
        del products
        index = cls()
        for product_id, edge in links.items():
            index._graph_product_ids.add(product_id)
            for zone_id in edge.get("zones") or []:
                for tier_id in edge.get("weight_tiers") or []:
                    key = (zone_id, tier_id)
                    index._by_edge.setdefault(key, []).append(product_id)
                    index._tiers_by_zone.setdefault(zone_id, set()).add(tier_id)
                    index._product_edges.setdefault(product_id, set()).add(key)
        return index

    def candidates(self, zone_id: str, weight_tier_id: str) -> list[str]:
        return list(self._by_edge.get((zone_id, weight_tier_id), []))

    def weight_tier_ids(self, zone_id: str) -> list[str]:
        return list(self._tiers_by_zone.get(zone_id, set()))

    def is_valid_edge(self, product_id: str, zone_id: str, weight_tier_id: str) -> bool:
        return product_id in self._by_edge.get((zone_id, weight_tier_id), [])

    def has_graph_edge(self, product_id: str) -> bool:
        return product_id in self._graph_product_ids
