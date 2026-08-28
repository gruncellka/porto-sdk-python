"""Authoritative quote composition — amount + complete components."""

from __future__ import annotations

import pytest

from porto_sdk.errors import PortoError, PortoErrorCode
from porto_sdk.execution import PortoMarkRequest
from porto_sdk.services.resolution.quote import compose_quote
from tests.support.bound_provider import bound_provider


@pytest.mark.offline
def test_resolve_amount_includes_bound_service_and_matches_price(client) -> None:
    bound = bound_provider(client)
    porto = bound.resolve(
        country_code="DE",
        weight=20,
        envelope_id="DL",
        services=["registered"],
        service_ids=["einschreiben"],
    )
    assert porto.product.id == "standardbrief"
    product = next(row for row in porto.components if row.kind == "product")
    service = next(row for row in porto.components if row.id == "einschreiben")
    assert product.amount == 95
    assert service.amount > 0
    assert porto.amount == product.amount + service.amount
    assert sum(row.amount for row in porto.components) == porto.amount

    pricing = bound.price(
        country_code="DE",
        weight=20,
        envelope_id="DL",
        services=["registered"],
        service_ids=["einschreiben"],
    )
    assert pricing.amount == porto.amount
    assert pricing.currency == porto.currency
    assert [(row.kind, row.id, row.amount) for row in pricing.components] == [
        (row.kind, row.id, row.amount) for row in porto.components
    ]


@pytest.mark.offline
@pytest.mark.asyncio
async def test_prepare_value_equals_porto_amount(client) -> None:
    bound = bound_provider(client)
    porto = bound.resolve(
        country_code="DE",
        weight=20,
        envelope_id="DL",
        services=["registered"],
        service_ids=["einschreiben"],
    )
    prepared = await bound._prepare(PortoMarkRequest(porto=porto))
    assert prepared.request.value == porto.amount
    assert prepared.pre_calculated_price == porto.amount


@pytest.mark.offline
def test_missing_bound_service_price_fails_closed(client, monkeypatch) -> None:
    bound = bound_provider(client)
    monkeypatch.setattr(bound._resolver, "get_service_price", lambda *_args, **_kw: None)
    with pytest.raises(PortoError) as exc:
        bound.resolve(
            country_code="DE",
            weight=20,
            envelope_id="DL",
            services=["registered"],
            service_ids=["einschreiben"],
        )
    assert exc.value.code == PortoErrorCode.PORTO_PRICE_NOT_FOUND
    assert exc.value.details["service_id"] == "einschreiben"

    with pytest.raises(PortoError) as price_exc:
        bound.price(
            country_code="DE",
            weight=20,
            envelope_id="DL",
            services=["registered"],
            service_ids=["einschreiben"],
        )
    assert price_exc.value.code == PortoErrorCode.PORTO_PRICE_NOT_FOUND


@pytest.mark.offline
def test_explicit_zero_service_price_is_a_component(client, monkeypatch) -> None:
    bound = bound_provider(client)
    monkeypatch.setattr(bound._resolver, "get_service_price", lambda *_args, **_kw: 0)
    porto = bound.resolve(
        country_code="DE",
        weight=20,
        envelope_id="DL",
        services=["registered"],
        service_ids=["einschreiben"],
    )
    service = next(row for row in porto.components if row.id == "einschreiben")
    assert service.amount == 0
    assert porto.amount == 95
    assert sum(row.amount for row in porto.components) == porto.amount


@pytest.mark.offline
def test_compose_quote_helper_sums_and_fails_closed() -> None:
    quote = compose_quote(
        product_id="standardbrief",
        product_amount=95,
        zone_id="domestic",
        weight_tier_id="W0020",
        service_ids=["einschreiben"],
        lookup_service_price=lambda _sid, _zone: 265,
    )
    assert quote.amount == 360
    assert [row.kind for row in quote.components] == ["product", "service"]

    with pytest.raises(PortoError) as exc:
        compose_quote(
            product_id="standardbrief",
            product_amount=95,
            zone_id="domestic",
            weight_tier_id="W0020",
            service_ids=["einschreiben"],
            lookup_service_price=lambda _sid, _zone: None,
        )
    assert exc.value.code == PortoErrorCode.PORTO_PRICE_NOT_FOUND
    assert exc.value.details["service_id"] == "einschreiben"
