"""Step definitions for pricing.feature."""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.bdd.steps.helpers import (
    product_reference_amount,
    public_price,
    resolve_price,
)


@given(parsers.parse("the weight is {weight:d} grams"))
@given(parsers.parse("I have weight {weight:d} grams"))
@given(parsers.parse("the letter weight is {weight:d} grams"))
def given_weight_grams(weight: int, context):
    context["weight"] = weight
    context["letter_weight"] = weight


@given(parsers.parse('I have product "{product_id}"'))
def given_product(product_id: str, context):
    context["product_id"] = product_id


@given(parsers.parse('I have zone "{zone_id}"'))
def given_zone(zone_id: str, context):
    context["zone_id"] = zone_id


@when("I calculate the price")
@when("I get the price")
def when_get_price(context):
    resolve_price(context)


@when("I calculate the price again with the same parameters")
@when("I get the price again with the same parameters")
def when_get_price_again(context):
    resolve_price(context)


@then("I should get a price in cents")
def then_price_in_cents(context):
    assert (context.get("price") or 0) > 0


@then(parsers.parse('the currency should be "{currency}"'))
def then_currency(currency: str, context):
    pricing = context.get("pricing")
    if isinstance(pricing, dict) and "currency" in pricing:
        assert pricing["currency"] == currency
        return
    if pricing is not None and hasattr(pricing, "currency"):
        assert pricing.currency == currency
        return
    resolved = context.get("resolved")
    if resolved is not None:
        assert getattr(resolved, "currency", None) == currency
        return
    assert context.get("result", {}).get("currency") == currency


@then(parsers.parse("the quoted amount should be {amount:d}"))
def then_quoted_amount_exact(amount: int, context):
    assert context["price"] == amount


@then(parsers.parse('the quoted product id should be "{product_id}"'))
def then_quoted_product_id(product_id: str, context):
    pricing = context.get("pricing")
    assert pricing is not None
    assert pricing.product_id == product_id


@then("the quoted components should sum to the quoted amount")
def then_quoted_components_sum(context):
    pricing = context.get("pricing")
    assert pricing is not None
    components = list(getattr(pricing, "components", []) or [])
    assert sum(row.amount for row in components) == pricing.amount


@then("the quoted amount should be higher than the domestic amount")
@then("the price should be higher than domestic price")
def then_price_higher_than_domestic(context):
    domestic = public_price(context, country_code="DE")
    assert context["price"] > domestic.amount


@then(parsers.parse('the quoted amount should be higher than the price of product "{product_id}"'))
def then_quoted_higher_than_product(product_id: str, context):
    assert context["price"] > product_reference_amount(context, product_id)


@then("the price should be greater than 0")
def then_price_greater_than_zero(context):
    assert (context.get("price") or 0) > 0


@then("I should store the result")
def then_store_result(context):
    context["stored_price"] = context.get("price")
    context["stored_pricing"] = context.get("pricing")


@then("the prices should be identical")
def then_prices_identical(context):
    assert context.get("stored_price") == context.get("price")


@given(parsers.parse('destination country "{country_code}"'))
def destination_country_outline(country_code: str, context):
    context["destination_country"] = country_code


@given(parsers.parse('zone id is "{zone_id}"'))
def zone_id_is(zone_id: str, context):
    context["zone_id"] = zone_id


@then(parsers.parse('the resolved zone id should be "{zone_id}"'))
def resolved_zone_id_should_be(zone_id: str, context):
    pricing = context.get("pricing")
    if pricing is not None:
        zone = getattr(pricing, "zone_id", None) or getattr(pricing, "zone", None)
        if zone is not None:
            assert zone == zone_id
            return
    resolved = context.get("resolved")
    assert resolved is not None, "expected resolved Porto or pricing with zone"
    assert resolved.zone.id == zone_id


@then("the price should be consistent with product and zone")
def price_consistent_with_product_zone(context):
    pricing = context.get("pricing")
    assert pricing is not None
    assert getattr(pricing, "product_id", None) or getattr(pricing, "product", None)
    zone = getattr(pricing, "zone_id", None) or getattr(pricing, "zone", None)
    assert zone
    expected_zone = context.get("expected_zone") or context.get("zone_id")
    if expected_zone is not None:
        zone_id = zone if isinstance(zone, str) else getattr(zone, "id", zone)
        assert zone_id == expected_zone
