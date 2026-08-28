"""
Product Resolver — data-driven product selection using the resolution graph.

Resolves a provider product from zone × weight_tier (+ optional envelope filter).
Uses resolution graph.json as the constraint graph — no provider branching.
Catalog identity is concrete ``id``.
"""

from collections.abc import Sequence
from typing import Any, Literal

from ...data.loader import PortoDataLoader, PortoProduct
from ...errors import PortoError, PortoErrorCode
from ...kinds import ServiceKind
from .delivery_resolver import DeliveryResolver
from .fingerprint import resolution_fingerprint
from .service_resolver import (
    bind_requested_services,
    product_matches_unmatched_kind,
    raise_service_unsupported,
)
from .types import ResolvedInput

DeliveryPreference = Literal["fastest", "cheapest", "economy"]


def _envelope_matches(product: PortoProduct, envelope_id: str | None) -> bool:
    if not envelope_id:
        return True
    wanted = envelope_id.strip().upper()
    allowed = [eid.upper() for eid in (product.envelope_ids or [])]
    if not allowed:
        return True
    return wanted in allowed


class ProductResolver:
    """
    Resolves products using resolution graph constraint graph.

    resolution graph defines valid combinations: product × zone × weight_tier.
    Products ≠ real-world availability — resolution graph is the source of truth.
    """

    def __init__(self, data_loader: PortoDataLoader, provider_id: str):
        self._loader = data_loader
        self._delivery_resolver = DeliveryResolver(data_loader, provider_id)

    def find_candidates(
        self,
        zone_id: str,
        weight_tier_id: str,
        envelope_id: str | None = None,
    ) -> list[PortoProduct]:
        index = self._loader.resolution_index
        if index is not None:
            product_ids = index.candidates(zone_id, weight_tier_id)
            candidates: list[PortoProduct] = []
            for product_id in product_ids:
                product = self._loader.get_product(product_id)
                if product is not None and _envelope_matches(product, envelope_id):
                    candidates.append(product)
            return candidates

        links = self._get_links()
        candidates = []
        for product in self._loader.get_all_products():
            if not self._is_resolvable_product(product):
                continue
            if not _envelope_matches(product, envelope_id):
                continue
            if self._is_valid_combination(product.id, zone_id, weight_tier_id, links):
                candidates.append(product)
        return candidates

    def resolve(self, input: ResolvedInput) -> PortoProduct | None:
        candidates = self.find_candidates(input.zone_id, input.weight_tier_id, input.envelope_id)
        return self.select_product(
            candidates,
            input.zone_id,
            input.weight_tier_id,
            product_id=input.product_id,
            delivery_preference=input.delivery_preference,
            indemnity_tier=input.indemnity_tier,
            strategy=self._graph_strategy(),
        )

    def apply_service_tokens(
        self,
        candidates: list[PortoProduct],
        tokens: list[str] | None,
        *,
        indemnity_tier: str | None = None,
        zone_id: str,
        weight_tier_id: str,
        kinds: Sequence[str] | None = None,
        service_ids: list[str] | None = None,
    ) -> tuple[list[PortoProduct], list[str], tuple[ServiceKind, ...]]:
        """Bind service kinds + catalog id pins; filter products for unmatched kinds."""
        product_id = candidates[0].id if len(candidates) == 1 else None
        bound, selected_kinds, unmatched = bind_requested_services(
            self._loader,
            kinds=kinds,
            service_ids=service_ids if service_ids is not None else tokens,
            zone_id=zone_id,
            product_id=product_id,
        )
        for kind in unmatched:
            narrowed = [
                product
                for product in candidates
                if product_matches_unmatched_kind(self._loader, product, kind)
            ]
            if not narrowed:
                raise_service_unsupported(
                    kind=kind,
                    zone_id=zone_id,
                    product_id=product_id,
                )
            candidates = narrowed
        if unmatched and any(k == "registered" for k in unmatched):
            indemnified = [p for p in candidates if p.indemnity]
            tiers = {p.indemnity.tier for p in indemnified if p.indemnity}
            if indemnified and not indemnity_tier and len(tiers) > 1:
                raise PortoError(
                    "Multiple registered products match; set indemnity_tier",
                    PortoErrorCode.PORTO_PRODUCT_AMBIGUOUS,
                    status_code=400,
                    details={
                        "zone": zone_id,
                        "weight_tier": weight_tier_id,
                        "candidate_ids": [p.id for p in indemnified],
                    },
                )
        return candidates, bound, tuple(selected_kinds)

    def _graph_strategy(self) -> str | None:
        graph = self._loader.resolution_graph
        return getattr(graph, "strategy", None)

    def select_product(
        self,
        candidates: list[PortoProduct],
        zone_id: str,
        weight_tier_id: str,
        *,
        product_id: str | None = None,
        delivery_preference: DeliveryPreference | None = None,
        indemnity_tier: str | None = None,
        strategy: str | None = None,
    ) -> PortoProduct | None:
        if not candidates:
            return None

        if product_id:
            narrowed = [p for p in candidates if p.id == product_id]
            if not narrowed:
                return None
            candidates = narrowed

        if indemnity_tier:
            narrowed = [p for p in candidates if p.indemnity and p.indemnity.tier == indemnity_tier]
            if not narrowed:
                return None
            candidates = narrowed

        if len(candidates) == 1:
            return candidates[0]

        effective_strategy = strategy or self._graph_strategy()
        preference = delivery_preference
        if not preference and effective_strategy == "speed":
            preference = "fastest"
        elif not preference and effective_strategy == "min":
            preference = "cheapest"

        if preference:
            selected = self._select_by_preference(candidates, zone_id, weight_tier_id, preference)
            if selected:
                return selected

        raise PortoError(
            "Multiple products match zone and weight tier",
            PortoErrorCode.PORTO_PRODUCT_AMBIGUOUS,
            status_code=400,
            details={
                "zone": zone_id,
                "weight_tier": weight_tier_id,
                "candidate_ids": [p.id for p in candidates],
            },
        )

    def is_valid_combination(self, product_id: str, zone_id: str, weight_tier_id: str) -> bool:
        index = self._loader.resolution_index
        if index is not None:
            return index.is_valid_edge(product_id, zone_id, weight_tier_id)
        links = self._get_links()
        return self._is_valid_combination(product_id, zone_id, weight_tier_id, links)

    def candidate_facts(self, product: PortoProduct, zone_id: str) -> dict[str, Any]:
        hint = self._delivery_resolver.resolve(product, zone_id)
        return {
            "product_id": product.id,
            "delivery_hint": hint,
            "fingerprint": resolution_fingerprint(product, zone_id),
            "included_features": list(product.included_features or []),
            "indemnity": (
                {"tier": product.indemnity.tier, "max_amount": product.indemnity.max_amount}
                if product.indemnity
                else None
            ),
            "tracking": product.tracking,
        }

    def _select_by_preference(
        self,
        candidates: list[PortoProduct],
        zone_id: str,
        weight_tier_id: str,
        preference: DeliveryPreference,
    ) -> PortoProduct | None:
        if preference == "cheapest":
            return self._select_cheapest(candidates, zone_id, weight_tier_id)

        if preference == "fastest":
            return min(
                candidates,
                key=lambda p: self._speed_sort_key(p, zone_id, fastest=True),
            )

        if preference == "economy":
            return max(
                candidates,
                key=lambda p: self._speed_sort_key(p, zone_id, economy=True),
            )

        return None

    def _select_cheapest(
        self,
        candidates: list[PortoProduct],
        zone_id: str,
        weight_tier_id: str,
    ) -> PortoProduct | None:
        best: PortoProduct | None = None
        best_price: int | None = None

        for product in candidates:
            pricing = self._loader.get_price_by_product_zone_weight_tier(
                product.id, zone_id, weight_tier_id
            )
            if pricing and (best_price is None or pricing.price < best_price):
                best = product
                best_price = pricing.price

        return best

    def _speed_sort_key(
        self,
        product: PortoProduct,
        zone_id: str,
        *,
        fastest: bool = False,
        economy: bool = False,
    ) -> tuple:
        hint = self._delivery_resolver.resolve(product, zone_id)
        if hint is None:
            if economy:
                return (-1, -1)
            return (999, 999) if fastest else (-1, -1)
        days_min = hint.days_min if hint.days_min is not None else hint.days_max
        if economy:
            return (hint.days_max, days_min)
        if fastest:
            return (hint.days_max, days_min)
        return (-hint.days_max, -days_min)

    def _get_links(self) -> dict:
        graph = self._loader.resolution_graph
        return getattr(graph, "links", None) or {}

    def _is_resolvable_product(self, product: PortoProduct) -> bool:
        index = self._loader.resolution_index
        if index is not None and index.has_graph_edge(product.id):
            return True
        return bool(
            product.mark_type == "stamp" or product.mark_type == "label" or product.envelope_ids
        )

    def _is_valid_combination(
        self, product_id: str, zone_id: str, weight_tier_id: str, links: dict
    ) -> bool:
        product_links = links.get(product_id, {})
        valid_zones = product_links.get("zones", [])
        valid_tiers = product_links.get("weight_tiers", [])
        return zone_id in valid_zones and weight_tier_id in valid_tiers
