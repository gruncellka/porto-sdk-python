"""
Step definitions for CLI BDD tests
Tests CLI functions directly (not via subprocess)
"""

import json

import pytest
from pydantic import ValidationError
from pytest_bdd import given, parsers, then, when

from porto_sdk.cli import get_config_summary, load_porto_config
from porto_sdk.data.porto_data_registry import PortoDataRegistry
from porto_sdk.errors import PortoError
from porto_sdk.types import Address, ValidationResult
from tests.bdd.steps.async_util import run_async
from tests.bdd.steps.helpers import (
    bound,
    country_for_zone,
    provider_home_country,
    provider_id_from_context,
    public_price,
)
from tests.support.addresses import address_json
from tests.support.porto_features_path import get_porto_data_path


def _address_from_json(data: dict) -> Address:
    return Address(
        name=str(data.get("name", "Test")),
        street=str(data["street"]),
        house_number=str(data.get("house_number", "1")),
        postal_code=str(data["postal_code"]),
        locality=str(data["locality"]),
        country_code=str(data["country_code"]),
        region_code=data.get("region_code"),
    )


def _validation_result_from_error(exc: Exception) -> ValidationResult:
    if isinstance(exc, ValidationError):
        errors = [str(err.get("msg", err)) for err in exc.errors()]
    else:
        errors = [str(exc)]
    return ValidationResult(is_valid=False, errors=errors, warnings=[])


def _sample_porto(context):
    client = bound(context)
    home = provider_home_country(context)
    try:
        return client.resolve(country_code=home, weight=20, product_id=context.get("product_id"))
    except PortoError:
        options = client.options(country_code=home, weight=20)
        assert options, f"no product options for {home}"
        return client.resolve(country_code=home, weight=20, product_id=options[0].id)


@given("I have porto-data available")
def porto_data_available(client, context):
    """Verify porto-data is available via public catalog surfaces."""
    if context.get("client") is None:
        context["client"] = client
    assert context["client"].envelopes.list()
    context["data_path"] = get_porto_data_path()


@given("I have a valid address JSON data")
def create_valid_address_data(context):
    """Create valid address data for testing"""
    context["address_data"] = address_json("valid_DE")


@when("I call CLI config command")
def call_cli_config(context):
    """Call CLI config command directly"""
    provider = provider_id_from_context(context) if context.get("provider_id") else None
    summary = get_config_summary(provider_override=provider)
    if provider:
        summary["provider"] = provider
    registry = PortoDataRegistry(load_porto_config())
    metadata = registry.get_metadata()
    context["cli_result"] = {
        **summary,
        "porto_data_version": (
            metadata.get("project", {}).get("version", "unknown") if metadata else "unknown"
        ),
    }


@when("I call CLI data info command")
def call_cli_data_info(context):
    """Call CLI data info command directly (uses registry for porto-data)"""
    registry = PortoDataRegistry(load_porto_config())
    metadata = registry.get_metadata()

    if metadata:
        context["cli_result"] = {
            "version": metadata.get("project", {}).get("version", "unknown"),
            "generated_at": metadata.get("generated_at", "unknown"),
            "entities": list(metadata.get("entities", {}).keys()),
        }
    else:
        context["cli_result"] = {"error": "metadata not found"}


@when("I call CLI data products command")
def call_cli_data_products(context):
    """List catalog products through public options()."""
    client = bound(context)
    home = provider_home_country(context)
    found: dict[str, dict[str, str]] = {}
    for weight in (20, 50, 100, 500, 1000, 2000):
        try:
            for row in client.options(country_code=home, weight=weight):
                found[row.id] = {"id": row.id, "name": row.name}
        except PortoError:
            continue
    context["cli_result"] = {"products": list(found.values())}


def _zone_probe_countries(context):
    home = provider_home_country(context)
    provider = provider_id_from_context(context)
    extras = {
        "deutschepost": ("FR", "US"),
        "laposte": ("BE", "US"),
        "ukrposhta": ("US",),
        "swisspost": ("DE", "US"),
    }.get(provider, ("US",))
    seen: set[str] = set()
    for code in (home, *extras):
        if code not in seen:
            seen.add(code)
            yield code


@when("I call CLI data zones command")
def call_cli_data_zones(context):
    """Collect zones through public resolve()."""
    client = bound(context)
    found: dict[str, dict[str, str]] = {}
    for country in _zone_probe_countries(context):
        try:
            porto = client.resolve(
                country_code=country, weight=20, product_id=context.get("product_id")
            )
        except (PortoError, ValueError):
            try:
                options = client.options(country_code=country, weight=20)
            except (PortoError, ValueError):
                continue
            if not options:
                continue
            try:
                porto = client.resolve(country_code=country, weight=20, product_id=options[0].id)
            except (PortoError, ValueError):
                continue
        found[porto.zone.id] = {"id": porto.zone.id, "name": porto.zone.name}
    context["cli_result"] = {"zones": list(found.values())}


@when("I call CLI data services command")
def call_cli_data_services(context):
    """List services from a public resolve() Porto."""
    porto = _sample_porto(context)
    context["cli_result"] = {
        "services": [{"id": row.id, "name": row.name} for row in porto.available_services]
    }


@when(parsers.parse('I call CLI restrictions command with country "{country}"'))
def call_cli_restrictions(country, context):
    result = context["client"].restrictions.check(country)
    context["cli_result"] = {
        "impact": result.impact,
        "legal": result.legal,
        "routing": result.routing,
    }


@when(
    parsers.parse(
        'I call CLI data price command with product "{product}" zone "{zone}" weight {weight:d}'
    )
)
def call_cli_data_price(product, zone, weight, context):
    provider = provider_id_from_context(context)
    country = country_for_zone(provider, zone)
    pricing = public_price(
        context,
        country_code=country,
        weight=weight,
        product_id=product,
    )
    context["cli_result"] = {
        "product": product,
        "zone": pricing.zone_id,
        "weight": weight,
        "price": pricing.amount,
        "currency": pricing.currency,
    }


def _cli_price_payload(context, country: str, weight: int) -> dict:
    resolved = bound(context).resolve(
        country_code=country,
        weight=weight,
        delivery_preference=context.get("delivery_preference"),
        product_id=context.get("product_id"),
    )
    return {
        "product": {"id": resolved.product.id, "name": resolved.product.name},
        "zone": {"id": resolved.zone.id, "name": resolved.zone.name},
        "amount": resolved.amount,
        "currency": resolved.currency,
        "is_valid": resolved.is_valid,
    }


@when(parsers.parse('I call CLI price command with country "{country}" weight {weight:d}'))
def call_cli_price(country, weight, context):
    context["cli_result"] = _cli_price_payload(context, country, weight)


@when(parsers.parse('I call CLI stamp simulate command with country "{country}" weight {weight:d}'))
def call_cli_stamp_simulate(country, weight, context):
    payload = _cli_price_payload(context, country, weight)
    context["cli_result"] = {
        "simulation": True,
        "product": payload["product"],
        "price": payload["amount"],
        "valid": payload["is_valid"],
    }


@when(
    parsers.parse(
        'I call CLI price command with type "{_ignored}" country "{country}" weight {weight:d}'
    )
)
def call_cli_price_with_type(_ignored, country, weight, context):
    del _ignored
    context["cli_result"] = _cli_price_payload(context, country, weight)


@when(
    parsers.parse(
        'I call CLI stamp simulate command with type "{_ignored}" country "{country}" weight {weight:d}'
    )
)
def call_cli_stamp_simulate_with_type(_ignored, country, weight, context):
    del _ignored
    payload = _cli_price_payload(context, country, weight)
    context["cli_result"] = {
        "simulation": True,
        "product": payload["product"],
        "price": payload["amount"],
        "valid": payload["is_valid"],
    }


@when("I call CLI validate address command")
def call_cli_validate_address(context):
    """Call CLI validate address command directly"""

    async def _run():
        address_data = context.get("address_data")
        if not address_data:
            pytest.fail("No address data in context")
        client = context["client"]
        try:
            address = _address_from_json(address_data)
        except (ValidationError, KeyError, ValueError) as exc:
            result = _validation_result_from_error(exc)
        else:
            result = await client.address.validate(address)
        context["cli_result"] = {
            "valid": result.is_valid,
            "errors": result.errors or [],
            "warnings": result.warnings or [],
        }

    run_async(_run())


@when("the result should be stored for comparison")
@then("the result should be stored for comparison")
def store_result_for_comparison(context):
    """Store result for later comparison"""
    context["previous_cli_result"] = context.get("cli_result")


def _result_payload(context) -> dict:
    cli = context.get("cli_result")
    if isinstance(cli, dict) and cli:
        return cli
    sdk = context.get("result")
    if isinstance(sdk, dict) and sdk:
        return sdk
    if isinstance(cli, dict):
        return cli
    if isinstance(sdk, dict):
        return sdk
    return {}


@then(parsers.parse('the result should have field "{field}"'))
def result_has_field(field, context):
    """Check if result has field"""
    result = _result_payload(context)
    assert field in result, f"Field '{field}' not found in result: {result}"


def _coerce_expected_value(value: str):
    if value.isdigit():
        return int(value)
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    return value


def _normalize_step_value(value: str):
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] == '"':
        cleaned = cleaned[1:-1]
    return _coerce_expected_value(cleaned)


@then(parsers.parse('the result should have field "{field}" with value {value}'))
def result_field_has_unquoted_value(field, value, context):
    """Check if result field has bool/number/string value (quoted or not)."""
    result = _result_payload(context)
    assert field in result, f"Field '{field}' not found in result"
    expected_value = _normalize_step_value(value)
    assert result[field] == expected_value, (
        f"Field '{field}' has value '{result[field]}', expected '{expected_value}'"
    )


@then(parsers.parse('the result should have field "{field}" as {type_name}'))
def result_field_is_type(field, type_name, context):
    """Check if result field is of specific type"""
    result = _result_payload(context)
    assert field in result, f"Field '{field}' not found in result"

    actual_value = result[field]
    type_map = {
        "number": (int, float),
        "string": str,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    expected_type = type_map.get(type_name.lower())
    assert expected_type is not None, f"Unknown type: {type_name}"

    assert isinstance(actual_value, expected_type), (
        f"Field '{field}' is {type(actual_value).__name__}, expected {type_name}"
    )


@then(
    parsers.parse(
        'the result should have field "{field}" with nested "{nested_field}" "{nested_value}"'
    )
)
def result_field_has_nested_value(field, nested_field, nested_value, context):
    """Check if result nested field has specific value"""
    result = context.get("cli_result", {})
    assert field in result, f"Field '{field}' not found in result"

    nested_data = result[field]
    assert isinstance(nested_data, dict), f"Field '{field}' is not an object"
    assert nested_field in nested_data, f"Nested field '{nested_field}' not found"

    actual_value = nested_data[nested_field]
    if nested_value.isdigit():
        expected_value = int(nested_value)
    elif nested_value.lower() in ("true", "false"):
        expected_value = nested_value.lower() == "true"
    else:
        expected_value = nested_value

    assert actual_value == expected_value, (
        f"Nested field '{nested_field}' has value '{actual_value}', expected '{expected_value}'"
    )


@then(parsers.parse('the result should have array "{field}"'))
def result_has_array(field, context):
    """Check if result has field as array"""
    result = context.get("cli_result", {})
    assert field in result, f"Field '{field}' not found in result: {result}"
    assert isinstance(result[field], list), f"Field '{field}' is not an array"


@then(parsers.parse('the {field} array should contain product with id "{product_id}"'))
def array_contains_product(field, product_id, context):
    """Check if products array contains product with id"""
    result = context.get("cli_result", {})
    assert field in result, f"Field '{field}' not found in result"

    products = result[field]
    assert isinstance(products, list), f"Field '{field}' is not an array"

    product_ids = [p.get("id") for p in products if isinstance(p, dict)]
    assert product_id in product_ids, (
        f"Product '{product_id}' not found in {field} array. Found: {product_ids}"
    )


@then("the products array should be stored for comparison")
def store_products_array(context):
    products = _result_payload(context).get("products", [])
    context["stored_product_ids"] = {row.get("id") for row in products if isinstance(row, dict)}


@then("the products array should differ from the stored products array")
def products_array_differs(context):
    products = _result_payload(context).get("products", [])
    current = {row.get("id") for row in products if isinstance(row, dict)}
    stored = context.get("stored_product_ids", set())
    assert current and current != stored, f"expected different product ids, got {current!r}"
    context["stored_product_ids"] = current


@then(parsers.parse("the errors array should not be empty"))
def errors_array_not_empty(context):
    """Check if errors array is not empty"""
    result = context.get("cli_result", {})
    assert "errors" in result, "Errors field not found in result"
    assert isinstance(result["errors"], list), "Errors is not an array"
    assert len(result["errors"]) > 0, "Errors array is empty"


@then("the results should be identical")
def results_identical(context):
    """Check if two results are identical"""
    first_result = context.get("previous_cli_result")
    last_result = context.get("cli_result")

    assert first_result is not None, "Previous result not found"
    assert last_result is not None, "Last result not found"

    assert first_result == last_result, (
        f"Results differ:\n"
        f"First: {json.dumps(first_result, indent=2)}\n"
        f"Last: {json.dumps(last_result, indent=2)}"
    )


@then("the results should have same structure")
def results_same_structure(context):
    """Check if two results have same structure"""
    first_result = context.get("previous_cli_result")
    last_result = context.get("cli_result")

    assert first_result is not None, "Previous result not found"
    assert last_result is not None, "Last result not found"

    first_keys = set(first_result.keys())
    last_keys = set(last_result.keys())
    assert first_keys == last_keys, (
        f"Result structures differ:\nFirst keys: {first_keys}\nLast keys: {last_keys}"
    )


@then(parsers.parse('the "{field}" fields should match'))
def result_fields_match(field, context):
    """Check if specific fields match in two results"""
    first_result = context.get("previous_cli_result")
    last_result = context.get("cli_result")

    assert first_result is not None, "Previous result not found"
    assert last_result is not None, "Last result not found"

    assert field in first_result, f"Field '{field}' not found in first result"
    assert field in last_result, f"Field '{field}' not found in last result"

    assert first_result[field] == last_result[field], (
        f"Field '{field}' differs:\nFirst: {first_result[field]}\nLast: {last_result[field]}"
    )
