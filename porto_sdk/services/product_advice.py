"""Catalog weight → product recommendation (hard AUTO_UPGRADE / soft larger_than_needed).

Reads max_weight from porto-data via PortoResolver — apps must not fork this policy.
"""

from __future__ import annotations

from collections.abc import Sequence

from .porto_resolver import PortoResolver
from .product_option_types import (
    Advice,
    AdviceReason,
)


class _CatalogProduct:
    __slots__ = ("id", "max_weight", "name")

    def __init__(self, product_id: str, name: str, max_weight: float | None):
        self.id = product_id
        self.name = name
        self.max_weight = max_weight


def _catalog_products(
    resolver: PortoResolver,
    candidate_product_ids: Sequence[str] | None = None,
) -> list[_CatalogProduct]:
    allow = set(candidate_product_ids) if candidate_product_ids else None
    rows: list[_CatalogProduct] = []
    for product in resolver.list_products():
        if allow is not None and product.id not in allow:
            continue
        constraints = resolver.get_product_constraints(product.id)
        max_weight = constraints.get("max_weight")
        if max_weight is not None:
            max_weight = float(max_weight)
        rows.append(_CatalogProduct(product.id, product.name, max_weight))
    rows.sort(key=lambda row: row.max_weight if row.max_weight is not None else float("inf"))
    return rows


def _eligible_for_weight(product: _CatalogProduct, weight: float) -> bool:
    return product.max_weight is None or weight <= product.max_weight


def suggest_product_for_weight(
    resolver: PortoResolver,
    weight: float,
    candidate_product_ids: Sequence[str] | None = None,
) -> _CatalogProduct | None:
    """Smallest catalog product whose max_weight still covers ``weight``."""
    eligible = [
        row
        for row in _catalog_products(resolver, candidate_product_ids)
        if _eligible_for_weight(row, weight)
    ]
    return eligible[0] if eligible else None


def recommend_product_for_weight(
    resolver: PortoResolver,
    *,
    weight: float,
    selected_product_id: str | None = None,
    candidate_product_ids: Sequence[str] | None = None,
) -> Advice:
    """
    Recommend product for billing weight.

    Hard: selected max exceeded + heavier peer → AUTO_UPGRADE.
    Soft: selected heavier than needed → KEEP + larger_than_needed.
    """
    selected_id = selected_product_id.strip() if selected_product_id else None
    if selected_id == "":
        selected_id = None
    products = _catalog_products(resolver, candidate_product_ids)
    suggested = suggest_product_for_weight(resolver, weight, candidate_product_ids)

    selected = (
        next((row for row in products if row.id == selected_id), None) if selected_id else None
    )

    if selected is None:
        fallback = suggested or (products[0] if products else None)
        effective_id = fallback.id if fallback else None
        upgrade = (
            "AUTO_UPGRADE" if effective_id is not None and effective_id != selected_id else "KEEP"
        )
        reason: AdviceReason | None = "weight_over" if upgrade == "AUTO_UPGRADE" else None
        return Advice(
            action=upgrade,
            selected_product_id=selected_id,
            effective_product_id=effective_id,
            suggested_product_id=suggested.id if suggested else None,
            reason=reason,
            selected_max_weight=None,
            suggested_max_weight=suggested.max_weight if suggested else None,
            selected_product_name=None,
            suggested_product_name=suggested.name if suggested else None,
        )

    weight_over = selected.max_weight is not None and weight > selected.max_weight

    if weight_over:
        upgrade = (
            "AUTO_UPGRADE" if suggested is not None and suggested.id != selected.id else "KEEP"
        )
        return Advice(
            action=upgrade,
            selected_product_id=selected.id,
            effective_product_id=suggested.id if upgrade == "AUTO_UPGRADE" else selected.id,  # type: ignore[union-attr]
            suggested_product_id=suggested.id if suggested else None,
            reason="weight_over",
            selected_max_weight=selected.max_weight,
            suggested_max_weight=suggested.max_weight if suggested else None,
            selected_product_name=selected.name,
            suggested_product_name=suggested.name if suggested else None,
        )

    reason = None
    if (
        suggested
        and suggested.id != selected.id
        and suggested.max_weight is not None
        and selected.max_weight is not None
        and selected.max_weight > suggested.max_weight
    ):
        reason = "larger_than_needed"

    return Advice(
        action="KEEP",
        selected_product_id=selected.id,
        effective_product_id=selected.id,
        suggested_product_id=suggested.id if suggested else None,
        reason=reason,
        selected_max_weight=selected.max_weight,
        suggested_max_weight=suggested.max_weight if suggested else None,
        selected_product_name=selected.name,
        suggested_product_name=suggested.name if suggested else None,
    )
