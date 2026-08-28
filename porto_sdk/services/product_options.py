"""Contextual product options from catalog facts (no inferred labels)."""

from __future__ import annotations

from typing import Any

from .porto_resolver import PortoResolver
from .product_option_types import (
    Estimate,
    ProductIndemnityOption,
    ProductOption,
)
from .resolution.delivery_resolver import DeliveryHint


def _as_delivery_hint(hint: Any) -> DeliveryHint | None:
    if hint is None or isinstance(hint, DeliveryHint):
        return hint
    return None


def _product_allowed_for_envelope(
    allowed_envelope_ids: list[str],
    envelope_id: str | None,
) -> bool:
    if not envelope_id:
        return True
    format_key = envelope_id.strip().upper()
    if not allowed_envelope_ids:
        return True
    return any(eid.upper() == format_key for eid in allowed_envelope_ids)


def _provider_currency(resolver: PortoResolver) -> str:
    graph = resolver.get_graph()
    unit = graph.get("unit", {}) if isinstance(graph, dict) else {}
    if isinstance(unit, dict) and unit.get("currency"):
        return str(unit["currency"])
    return "EUR"


def _quote_currency(resolver: PortoResolver, pricing: Any) -> str:
    row = getattr(pricing, "currency", None) if pricing is not None else None
    if isinstance(row, str) and row.strip():
        return row.strip().upper()
    return _provider_currency(resolver)


def _indemnity_from_facts(indemnity: Any) -> ProductIndemnityOption | None:
    if not indemnity or not isinstance(indemnity, dict):
        return None
    tier = indemnity.get("tier")
    max_amount = indemnity.get("max_amount")
    if tier is None or max_amount is None:
        return None
    return ProductIndemnityOption(tier=str(tier), max_amount=int(max_amount))


def list_product_options(
    resolver: PortoResolver,
    *,
    country_code: str,
    weight: int,
    envelope_id: str | None = None,
) -> list[ProductOption]:
    zone = resolver.resolve_zone(country_code.strip().upper())
    weight_tier_id = resolver.weight_tier_resolver.resolve(weight)
    if not weight_tier_id:
        return []

    product_resolver = resolver.product_resolver
    provider_id = resolver.context.provider_id
    options: list[ProductOption] = []

    for product in resolver.list_products():
        constraints = resolver.get_product_constraints(product.id)
        allowed = list(constraints.get("allowed_envelope_ids") or [])
        if not _product_allowed_for_envelope(allowed, envelope_id):
            continue
        if not product_resolver.is_valid_combination(product.id, zone.id, weight_tier_id):
            continue

        pricing = resolver.get_price_by_product_zone_weight_tier(
            product.id, zone.id, weight_tier_id
        )
        facts = product_resolver.candidate_facts(product, zone.id)
        max_weight = constraints.get("max_weight")

        options.append(
            ProductOption(
                id=product.id,
                provider_id=provider_id,
                name=product.name,
                allowed_envelope_ids=allowed,
                mark_type=product.mark_type,
                tracking=product.tracking,
                max_weight=int(max_weight) if max_weight is not None else None,
                indemnity=_indemnity_from_facts(facts.get("indemnity")),
                amount=int(pricing.price) if pricing is not None else None,
                currency=_quote_currency(resolver, pricing),
                delivery_hint=_as_delivery_hint(facts.get("delivery_hint")),
                services=resolver.list_service_options_for_product_zone(product.id, zone.id),
            )
        )

    return options


def estimate_for_product(
    resolver: PortoResolver,
    *,
    product_id: str,
    country_code: str,
    weight: int,
) -> Estimate:
    from ..errors import PortoError, PortoErrorCode
    from ..errors.domains.resolution import raise_too_heavy

    zone = resolver.resolve_zone(country_code.strip().upper())
    weight_tier_id = resolver.weight_tier_resolver.resolve(weight)
    if not weight_tier_id:
        raise_too_heavy(
            f"Weight {weight} does not match any weight tier",
            weight=weight,
            status_code=400,
        )

    product = resolver.get_product(product_id)
    if product is None:
        raise PortoError(
            f"Unknown product: {product_id}",
            PortoErrorCode.PORTO_DATA_NOT_FOUND,
            status_code=404,
            retryable=False,
        )

    if not resolver.product_resolver.is_valid_combination(product.id, zone.id, weight_tier_id):
        raise PortoError(
            f"Product {product_id} not valid for zone {zone.id} and weight tier {weight_tier_id}",
            PortoErrorCode.PORTO_PRODUCT_NOT_FOUND,
            status_code=422,
            retryable=False,
        )

    pricing = resolver.get_price_by_product_zone_weight_tier(product.id, zone.id, weight_tier_id)
    if pricing is None:
        raise PortoError(
            f"No tariff for {product_id} / {zone.id} / {weight_tier_id}",
            PortoErrorCode.PORTO_PRICE_NOT_FOUND,
            status_code=404,
            retryable=False,
        )

    facts = resolver.product_resolver.candidate_facts(product, zone.id)
    return Estimate(
        product_id=product.id,
        zone_id=zone.id,
        weight_tier_id=weight_tier_id,
        weight=weight,
        amount=int(pricing.price),
        currency=_quote_currency(resolver, pricing),
        delivery_hint=_as_delivery_hint(facts.get("delivery_hint")),
    )
