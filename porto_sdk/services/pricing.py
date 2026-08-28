"""Pricing — public consumer price from destination facts."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..kinds import ServiceKind
from .porto_resolver import PortoResolver, ResolutionRequest
from .resolution.quote import PriceComponent
from .resolution.types import DeliveryPreference


class Pricing(BaseModel):
    """Price for a known zone (pricing-only; not PortoResolution)."""

    product_id: str
    zone_id: str
    weight: int
    amount: int
    currency: str = "EUR"
    components: list[PriceComponent] = Field(default_factory=list)


class PriceInput(BaseModel):
    """Public consumer price() input — destination facts, not catalog zone_id."""

    weight: int
    country_code: str
    product_id: str | None = None
    envelope_id: str | None = None
    indemnity_tier: str | None = None
    services: list[ServiceKind] | None = None
    service_ids: list[str] | None = None
    delivery_preference: DeliveryPreference | None = None

    model_config = {"extra": "forbid"}


def price(
    resolver: PortoResolver,
    *,
    weight: int,
    country_code: str,
    product_id: str | None = None,
    envelope_id: str | None = None,
    indemnity_tier: str | None = None,
    services: list[ServiceKind] | None = None,
    service_ids: list[str] | None = None,
    delivery_preference: DeliveryPreference | None = None,
) -> Pricing:
    """Public consumer price from destination facts — not catalog zone_id."""
    porto = resolver.resolve(
        ResolutionRequest(
            country_code=country_code,
            weight=weight,
            product_id=product_id,
            envelope_id=envelope_id,
            indemnity_tier=indemnity_tier,
            services=services,
            service_ids=service_ids,
            delivery_preference=delivery_preference,
        )
    )
    return Pricing(
        product_id=porto.product.id,
        zone_id=porto.zone.id,
        weight=weight,
        amount=porto.amount,
        currency=porto.currency,
        components=list(porto.components),
    )
