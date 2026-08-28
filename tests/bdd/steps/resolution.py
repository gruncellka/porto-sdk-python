"""Step definitions for resolution.feature and delivery_resolution.feature."""

from pytest_bdd import given, parsers, then, when

from porto_sdk.errors import PortoError, PortoErrorCode
from tests.bdd.steps.helpers import public_price, public_resolve


@given("I have a Porto SDK client initialized")
def client_initialized(client, context):
    """Use session client when provider step has not already set one."""
    if context.get("client") is None:
        context["client"] = client


@given("I have access to porto-data")
def porto_data_available(context):
    assert context.get("client") is not None
    assert context["client"].envelopes.list()


@given(parsers.parse('I want to send a letter to country "{country_code}"'))
def set_destination_country(country_code, context):
    context["destination_country"] = country_code


@given(parsers.parse('provider is "{provider}"'))
def set_provider(provider, client, context):
    from porto_sdk import PortoClient
    from porto_sdk.config import PortoConfig, ProviderRuntimeConfig
    from tests.support.porto_features_path import get_porto_data_path

    cfg = PortoConfig(
        providers={provider: ProviderRuntimeConfig()},
        data=get_porto_data_path(),
    )
    context["provider_id"] = provider
    context["client"] = PortoClient(cfg)


@given(parsers.parse("the letter weight is {weight:d} grams"))
def set_letter_weight(weight, context):
    context["letter_weight"] = weight


@given(parsers.parse('delivery preference is "{preference}"'))
def set_delivery_preference(preference, context):
    context["delivery_preference"] = preference


@given(parsers.parse('product id is "{product_id}"'))
def set_product_id(product_id, context):
    context["product_id"] = product_id


@given(parsers.parse('service ids are "{raw}"'))
def set_service_ids(raw, context):
    token = (raw or "").strip()
    if not token or token.lower() in {"none", "-", "null"}:
        context["service_ids"] = []
        return
    context["service_ids"] = [part.strip() for part in token.split(",") if part.strip()]


@when("I resolve the shipping configuration")
@when("I resolve the letter")
def resolve_shipping_configuration(context):
    try:
        context["resolved"] = public_resolve(context)
        context["resolution_error"] = None
    except PortoError as exc:
        context["resolved"] = None
        context["resolution_error"] = exc


@then(parsers.parse('I should get product with id "{product_id}"'))
def verify_product_id(product_id, context):
    assert context["resolved"].product.id == product_id


@then(parsers.parse('I should get zone with id "{zone_id}"'))
def verify_zone_id(zone_id, context):
    assert context["resolved"].zone.id == zone_id


@then(parsers.parse('I should get weight tier "{weight_tier_id}"'))
def verify_weight_tier(weight_tier_id, context):
    tier = context["resolved"].weight_tier
    tier_id = tier.get("id") if isinstance(tier, dict) else getattr(tier, "id", None)
    assert tier_id == weight_tier_id


@then("the resolution should be valid")
def verify_resolution_valid(context):
    assert context["resolved"].is_valid is True


@then("the resolution should be invalid")
def verify_resolution_invalid(context):
    assert context["resolution_error"] is not None


@then(parsers.parse('I should get Porto error code "{code}"'))
def verify_porto_error_code(code, context):
    exc = context.get("resolution_error") or context.get("mark_error")
    assert exc is not None
    observed = getattr(exc, "code", None)
    if hasattr(observed, "value"):
        observed = observed.value
    elif isinstance(exc, dict):
        observed = exc.get("code")
    assert str(observed) == code


@then("the resolution should include base price")
@then("the resolved amount should be a positive number")
def verify_resolved_amount_present(context):
    assert context["resolved"].amount > 0


@then("the base price should be a positive number")
def verify_base_price_positive(context):
    assert context["resolved"].amount > 0


@then("the resolved Porto should have a product id")
def verify_resolved_has_product_id(context):
    assert context["resolved"].product.id


@then("the resolved Porto should include a restrictions result")
def verify_resolved_has_restrictions(context):
    restrictions = context["resolved"].restrictions
    assert restrictions is not None
    assert hasattr(restrictions, "impact")
    assert hasattr(restrictions, "legal")
    assert hasattr(restrictions, "routing")
    assert restrictions.impact in (None, "block", "warn")
    assert isinstance(restrictions.legal, tuple)
    assert isinstance(restrictions.routing, tuple)


@then("the quoted amount should equal the resolved amount")
def verify_quoted_equals_resolved(context):
    pricing = public_price(context) if context.get("pricing") is None else context["pricing"]
    amount = getattr(pricing, "amount", None)
    if amount is None and isinstance(pricing, dict):
        amount = pricing.get("amount")
    if amount is None:
        amount = context.get("price") or context.get("quoted_amount")
    assert amount == context["resolved"].amount


@then(parsers.parse('the resolved Porto should include service kind "{kind}"'))
def verify_resolved_service_kind(kind, context):
    assert kind in context["resolved"].services


@then(parsers.parse('the resolved Porto should include service id "{service_id}"'))
def verify_resolved_service_id(service_id, context):
    assert service_id in context["resolved"].service_ids


@then(parsers.parse('the resolved Porto should include feature kind "{feature_kind}"'))
def verify_resolved_feature_kind(feature_kind, context):
    kinds = {getattr(row, "kind", None) for row in context["resolved"].features}
    assert feature_kind in kinds


@then("the resolved amount should be greater than the product component amount")
def verify_amount_includes_services(context):
    porto = context["resolved"]
    product_amount = next(row.amount for row in porto.components if row.kind == "product")
    assert porto.amount > product_amount


@given("a concrete product id is pinned from catalog options")
def pin_product_from_options(context):
    from tests.bdd.steps.helpers import bound, provider_home_country

    client = bound(context)
    country = context.get("destination_country") or provider_home_country(context)
    weight = context.get("letter_weight", 20)
    options = client.options(country_code=country, weight=weight)
    if not options:
        raise AssertionError(f"no product options for {country} at {weight}g")
    context["product_id"] = options[0].id
    context["pinned_product_id"] = options[0].id


@then("the resolved Porto should have the pinned product id")
def verify_pinned_product_id(context):
    assert context["resolved"].product.id == context["pinned_product_id"]


@then("the resolved Porto components should sum to the resolved amount")
def verify_components_sum_to_amount(context):
    porto = context["resolved"]
    total = sum(row.amount for row in porto.components)
    assert total == porto.amount


@then(parsers.parse('the resolved Porto should include currency "{currency}"'))
def verify_resolved_currency(currency, context):
    assert context["resolved"].currency == currency


@then("the resolved currency is present")
def verify_currency_present(context):
    currency = getattr(context["resolved"], "currency", None)
    assert isinstance(currency, str) and currency.strip()


@then(parsers.parse('the resolution should include currency "{currency}"'))
def verify_currency(currency, context):
    assert context["resolved"].currency == currency


@then(parsers.parse('delivery hint span should be "{span}"'))
def verify_delivery_span(span, context):
    assert context["resolved"].delivery_hint.span == span


@then(parsers.parse("delivery hint days max should be {days_max:d}"))
def verify_delivery_days_max(days_max, context):
    assert context["resolved"].delivery_hint.days_max == days_max


@then(parsers.parse('delivery hint weekdays should be "{weekdays}"'))
def verify_delivery_weekdays(weekdays, context):
    assert context["resolved"].delivery_hint.working_days.weekdays == weekdays


@then("resolution should be product ambiguous")
def verify_product_ambiguous(context):
    assert context["resolution_error"].code == PortoErrorCode.PORTO_PRODUCT_AMBIGUOUS
