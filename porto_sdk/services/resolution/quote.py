"""Compose an authoritative catalog quote from product + bound service rows."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from ...errors.domains.resolution import raise_price_not_found


class PriceComponent(BaseModel):
    """One catalog contribution to a quote. Generic kinds only."""

    kind: Literal["product", "service"]
    id: str
    amount: int


@dataclass(frozen=True)
class ComposedQuote:
    amount: int
    components: tuple[PriceComponent, ...]


def compose_quote(
    *,
    product_id: str,
    product_amount: int,
    zone_id: str,
    weight_tier_id: str,
    service_ids: Sequence[str],
    lookup_service_price: Callable[[str, str], int | None],
) -> ComposedQuote:
    """Sum product cents and every bound service. Missing service price fails closed."""
    components: list[PriceComponent] = [
        PriceComponent(kind="product", id=product_id, amount=int(product_amount))
    ]
    seen: set[str] = set()
    for raw in service_ids:
        service_id = str(raw or "").strip()
        if not service_id or service_id in seen:
            continue
        seen.add(service_id)
        price = lookup_service_price(service_id, zone_id)
        if price is None:
            raise_price_not_found(
                f"No price for service {service_id} / {zone_id}",
                product_id=product_id,
                zone_id=zone_id,
                weight_tier_id=weight_tier_id,
                status_code=422,
                details={"service_id": service_id},
            )
        components.append(PriceComponent(kind="service", id=service_id, amount=int(price)))
    return ComposedQuote(
        amount=sum(row.amount for row in components),
        components=tuple(components),
    )
