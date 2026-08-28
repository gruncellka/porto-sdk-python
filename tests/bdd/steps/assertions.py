"""Shared Then-step assertions for BDD scenarios."""

from __future__ import annotations

from pytest_bdd import parsers, then


def _items(context: dict, key: str) -> list:
    value = context.get(key)
    assert isinstance(value, list), f"Expected list at context[{key!r}]"
    return value


@then("I should get an array of products")
def array_of_products(context):
    _items(context, "products")


@then("I should get an array of zones")
def array_of_zones(context):
    _items(context, "zones")


@then("I should get an array of services")
def array_of_services(context):
    _items(context, "services")


@then("I should get an array of features")
def array_of_features(context):
    _items(context, "features")


@then("I should get an array of envelopes")
def array_of_envelopes(context):
    _items(context, "envelopes")


@then(parsers.parse('the products array should contain product with id "{product_id}"'))
def products_contain(product_id: str, context):
    cli = context.get("cli_result", {})
    if isinstance(cli.get("products"), list):
        ids = {item.get("id") for item in cli["products"] if isinstance(item, dict)}
    else:
        ids = {item["id"] for item in _items(context, "products")}
    assert product_id in ids


@then(parsers.parse('the zones array should contain zone with id "{zone_id}"'))
def zones_contain(zone_id: str, context):
    cli = context.get("cli_result", {})
    if isinstance(cli.get("zones"), list):
        ids = {item.get("id") for item in cli["zones"] if isinstance(item, dict)}
    else:
        ids = {item["id"] for item in _items(context, "zones")}
    assert zone_id in ids


@then(parsers.parse('the services array should contain service with id "{service_id}"'))
def services_contain(service_id: str, context):
    cli = context.get("cli_result", {})
    if isinstance(cli.get("services"), list):
        ids = {item.get("id") for item in cli["services"] if isinstance(item, dict)}
    else:
        ids = {item["id"] for item in _items(context, "services")}
    assert service_id in ids


@then(parsers.parse('the envelopes array should contain envelope with id "{envelope_id}"'))
def envelopes_contain(envelope_id: str, context):
    ids = {item["id"] for item in _items(context, "envelopes")}
    assert envelope_id in ids


@then(parsers.parse('the features array should contain feature with id "{feature_id}"'))
def features_contain(feature_id: str, context):
    ids = {item["id"] for item in _items(context, "features")}
    assert feature_id in ids


@then(parsers.parse('each product should have field "{field}"'))
def each_product_has_field(field: str, context):
    for item in _items(context, "products"):
        assert field in item


@then(parsers.parse('each zone should have field "{field}"'))
def each_zone_has_field(field: str, context):
    for item in _items(context, "zones"):
        assert field in item


@then(parsers.parse('each service should have field "{field}"'))
def each_service_has_field(field: str, context):
    for item in _items(context, "services"):
        assert field in item


@then(parsers.parse('each envelope should have field "{field}"'))
def each_envelope_has_field(field: str, context):
    for item in _items(context, "envelopes"):
        if isinstance(item, dict):
            assert field in item
        else:
            assert hasattr(item, field), f"assert {field!r} in {item!r}"


@then(parsers.parse('each feature should have field "{field}"'))
def each_feature_has_field(field: str, context):
    for item in _items(context, "features"):
        assert field in item


@then(parsers.parse('each price entry should have field "{field}"'))
def each_price_entry_has_field(field: str, context):
    for item in _items(context, "price_entries"):
        assert field in item


@then(parsers.parse('each price entry should have field "{field}" as {type_name}'))
def each_price_entry_field_type(field: str, type_name: str, context):
    type_map = {"number": (int, float), "array": list, "string": str}
    expected = type_map[type_name.lower()]
    for item in _items(context, "price_entries"):
        assert field in item
        assert isinstance(item[field], expected)


@then(parsers.parse('each price in array should have field "{field}"'))
def each_price_in_array_has_field(field: str, context):
    for item in _items(context, "nested_prices"):
        assert field in item


@then(parsers.parse('each price in array should have field "{field}" as {type_name}'))
def each_nested_price_field_type(field: str, type_name: str, context):
    type_map = {"number": (int, float)}
    expected = type_map[type_name.lower()]
    for item in _items(context, "nested_prices"):
        assert field in item
        assert isinstance(item[field], expected)


@then(parsers.parse('each restriction should have field "{field}"'))
def each_restriction_has_field(field: str, context):
    for item in _items(context, "restriction_entries"):
        assert field in item


@then(parsers.parse('each weight tier should have field "{field}"'))
def each_weight_tier_has_field(field: str, context):
    for item in _items(context, "weight_tier_entries"):
        assert field in item


def _result_payload(context: dict) -> dict:
    cli = context.get("cli_result")
    if isinstance(cli, dict):
        return cli
    result = context.get("result")
    if isinstance(result, dict):
        return result
    return {}


@then(parsers.parse('the result should have field "{field}" with value "{value}"'))
def result_field_value(field: str, value: str, context):
    result = _result_payload(context)
    assert field in result, f"Field '{field}' not found in result: {result}"
    actual = result[field]
    if value.isdigit():
        assert actual == int(value)
    elif value.lower() in ("true", "false"):
        assert actual == (value.lower() == "true")
    else:
        assert str(actual) == value


@then(parsers.parse('the result should have field "{field}" as {type_name}'))
def result_field_type(field: str, type_name: str, context):
    result = _result_payload(context)
    assert field in result, f"Field '{field}' not found in result: {result}"
    type_map = {"number": (int, float), "array": list, "string": str, "boolean": bool}
    expected = type_map[type_name.lower()]
    assert isinstance(result[field], expected)


@then(parsers.parse('restrictions should have field "{field}"'))
def restrictions_have_field(field: str, context):
    restrictions = context.get("restrictions_data", {})
    assert field in restrictions


@then(parsers.parse('restrictions should have array "{field}"'))
def restrictions_have_array(field: str, context):
    restrictions = context.get("restrictions_data", {})
    assert isinstance(restrictions.get(field), list)


@then(parsers.parse('providers should include provider "{provider_id}"'))
def providers_include(provider_id: str, context):
    providers = context.get("providers_data", {})
    provider_ids = {p["id"] for p in providers.get("providers", [])}
    assert provider_id in provider_ids


@then(parsers.parse('prices should have structure for product "{product_id}"'))
def prices_have_product(product_id: str, context):
    rows = context.get("product_prices", [])
    assert any(row.get("product_id") == product_id for row in rows)


@then(parsers.parse('weight tiers should contain tier "{tier_id}"'))
def weight_tiers_contain(tier_id: str, context):
    tiers = context.get("weight_tiers", {})
    assert tier_id in tiers


@then("I should get a price in cents")
def price_in_cents(context):
    assert context.get("price", 0) > 0


@then(parsers.parse('the currency should be "{currency}"'))
def verify_currency(currency: str, context):
    pricing = context.get("pricing")
    if pricing is not None and hasattr(pricing, "currency"):
        assert pricing.currency == currency
        return
    if pricing is not None and isinstance(pricing, dict) and "currency" in pricing:
        assert pricing["currency"] == currency
        return
    resolved = context.get("resolved")
    assert resolved is not None
    assert resolved.currency == currency


@then("I should get a pre-calculated price in cents")
def pre_calculated_price_cents(context):
    if "pre_calculated_price" in context:
        assert isinstance(context["pre_calculated_price"], int)
        return
    assert context.get("price", 0) > 0


@then("the pre-calculated price should be greater than 0")
def pre_calculated_price_positive(context):
    if "pre_calculated_price" in context:
        assert context["pre_calculated_price"] > 0
        return
    assert context.get("price", 0) > 0


@then("the price should be greater than 0")
def price_greater_than_zero(context):
    assert context.get("price", 0) > 0


@then("I should store the result")
def store_result(context):
    context["stored_price"] = context.get("price")
    context["stored_pricing"] = context.get("pricing")


@then("the prices should be identical")
def prices_identical(context):
    assert context.get("stored_price") == context.get("price")
