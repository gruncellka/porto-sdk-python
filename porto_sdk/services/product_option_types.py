"""Public types for product options, estimates, and weight advice."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..execution import MarkType, TrackingMode
from ..kinds import ServiceKind
from .resolution.delivery_resolver import DeliveryHint


class ProductIndemnityOption(BaseModel):
    tier: str
    max_amount: int


class ServiceOption(BaseModel):
    """Priced add-on available for a product × destination zone (from options())."""

    id: str
    kind: ServiceKind | None
    name: str
    amount: int | None
    currency: str
    label: str | None = None
    combinable_with: list[str] | None = None


class ProductOption(BaseModel):
    id: str
    provider_id: str
    name: str
    mark_type: MarkType | None
    tracking: TrackingMode | None
    currency: str
    allowed_envelope_ids: list[str] = Field(default_factory=list)
    max_weight: int | None = None
    indemnity: ProductIndemnityOption | None = None
    amount: int | None = None
    delivery_hint: DeliveryHint | None = None
    services: list[ServiceOption] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}


class Estimate(BaseModel):
    product_id: str
    zone_id: str
    weight_tier_id: str
    weight: int
    amount: int
    currency: str
    delivery_hint: DeliveryHint | None = None

    model_config = {"arbitrary_types_allowed": True}


AdviceAction = Literal["KEEP", "AUTO_UPGRADE"]
AdviceReason = Literal["weight_over", "larger_than_needed"]


class Advice(BaseModel):
    """Catalog weight advice — hard AUTO_UPGRADE or soft larger_than_needed."""

    action: AdviceAction
    selected_product_id: str | None = None
    effective_product_id: str | None = None
    suggested_product_id: str | None = None
    reason: AdviceReason | None = None
    selected_max_weight: float | None = None
    suggested_max_weight: float | None = None
    selected_product_name: str | None = None
    suggested_product_name: str | None = None
