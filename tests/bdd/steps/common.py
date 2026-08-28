"""
Canonical BDD vocabulary aliases shared with porto-features.

These steps intentionally avoid SDK business logic changes; they only normalize
phrasing so semantically equivalent Given/When/Then variants resolve to a
single behavior contract.
"""

from pytest_bdd import given, parsers, then, when

from tests.bdd.steps.helpers import public_price, public_resolve
from tests.support.addresses import address_from_fixture


@given("a sender")
@given("a valid sender")
@given("a domestic sender")
@given("valid origin address")
def given_sender(context):
    context["sender"] = address_from_fixture("origin_DE")


@given("a recipient")
@given("valid destination address")
def given_recipient(context):
    context["recipient"] = address_from_fixture("valid_DE")


@given(parsers.parse('a letter product "{product_id}"'))
def given_letter_product(product_id: str, context):
    context["product_id"] = product_id


@given(parsers.parse("weight {weight:d} grams"))
@given(parsers.parse("I have weight {weight:d} grams"))
@given(parsers.parse("I have a letter with weight {weight:d} grams"))
def given_weight(weight: int, context):
    context["weight"] = weight
    context["letter_weight"] = weight


@when("calculate postage")
def when_calculate_postage(context):
    pricing = public_price(context)
    context["pricing"] = pricing
    context["price"] = pricing.amount
    context["quoted_amount"] = pricing.amount


@then("price should be returned")
def then_price_returned(context):
    assert "price" in context
    assert isinstance(context["price"], int)
    assert context["price"] > 0


@given(parsers.parse('the destination country is "{country_code}"'))
def given_destination_country_alias(country_code: str, context):
    context["destination_country"] = country_code


@given(parsers.parse('service kind is "{kind}"'))
def given_service_kind(kind: str, context):
    kinds = list(context.get("services_kinds") or [])
    kinds.append(kind)
    context["services_kinds"] = kinds
    context["service_kind"] = kind


@given("I have a letter with base price")
def given_letter_with_base_price(context):
    resolved = public_resolve(context)
    context["resolved"] = resolved
    context["price"] = resolved.amount
    context["pricing"] = resolved
    context["quoted_amount"] = resolved.amount


@when("I add the service to the order")
def when_add_service_to_order(context):
    service_id = context.get("requested_service")
    assert service_id
    order = context.setdefault("order", {"services": []})
    order["services"].append(service_id)


@then(parsers.parse('the order should include service "{service_id}"'))
def then_order_includes_service(service_id: str, context):
    assert service_id in context["order"]["services"]


@then(parsers.parse('the resolved product id should be "{product_id}"'))
def then_resolved_product_id(product_id: str, context):
    assert context.get("resolved_product_id") == product_id
