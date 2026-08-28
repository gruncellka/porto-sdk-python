"""Step definitions for validation.feature."""

from __future__ import annotations

from pydantic import ValidationError
from pytest_bdd import given, parsers, then, when

from porto_sdk import Address
from porto_sdk.errors import PortoErrorCode
from tests.bdd.steps.async_util import run_async
from tests.support.addresses import load_address_fixture


@given(parsers.parse("length {length:d} mm"))
def given_length(length: int, context):
    context["letter_length"] = length


@given(parsers.parse("width {width:d} mm"))
def given_width(width: int, context):
    context["letter_width"] = width


@given(parsers.parse("height {height:d} mm"))
def given_height(height: int, context):
    context["letter_height"] = height


@given("valid origin address")
def valid_origin(context):
    context["origin_address"] = load_address_fixture("origin_DE")


@given("invalid destination address")
def invalid_destination(context):
    context["destination_address"] = {
        "id": "invalid",
        "country_code": "DE",
        "postal_code": "",
        "locality": "",
        "street": "",
    }


@given(parsers.parse('I have an address with name "{name}"'))
def address_with_name(name: str, context):
    context["address"] = {"name": name}


@given(parsers.parse('street "{street}"'))
def address_street(street: str, context):
    context["address"]["street"] = street


@given(parsers.parse('house number "{house_number}"'))
def address_house_number(house_number: str, context):
    context["address"]["house_number"] = house_number


@given(parsers.parse('postal code "{postal_code}"'))
def address_postal_code(postal_code: str, context):
    context["address"]["postal_code"] = postal_code


@given(parsers.parse('locality "{locality}"'))
def address_locality(locality: str, context):
    context["address"]["locality"] = locality


@given(parsers.parse('country code "{country_code}"'))
def address_country_code(country_code: str, context):
    context["address"]["country_code"] = country_code


@given("missing street")
def missing_street(context):
    context["address"]["street"] = ""


@given("missing postal code")
def missing_postal_code(context):
    context["address"]["postal_code"] = ""


@when("I validate the address")
def validate_address_feature(context):
    async def _validate():
        client = context["client"]
        address_data = context.get("address") or context.get("destination_address") or {}
        try:
            address = Address(
                name=address_data.get("name", "Test"),
                street=address_data.get("street"),
                house_number=address_data.get("house_number"),
                post_box=address_data.get("post_box"),
                postal_code=address_data.get("postal_code", ""),
                locality=address_data.get("locality", ""),
                country_code=address_data.get("country_code", ""),
                region_code=address_data.get("region_code"),
            )
        except ValidationError as exc:
            context["validation_result"] = type(
                "ValidationResult",
                (),
                {
                    "is_valid": False,
                    "errors": [err.get("msg", str(err)) for err in exc.errors()],
                    "warnings": [],
                },
            )()
            context["validation_errors"] = context["validation_result"].errors
            context["validation_warnings"] = []
            return
        result = await client.address.validate(address)
        context["validation_result"] = result
        context["validation_errors"] = result.errors or []
        context["validation_warnings"] = result.warnings or []

    run_async(_validate())


@then("the validation should pass")
def validation_pass(context):
    result = context["validation_result"]
    assert result.is_valid if hasattr(result, "is_valid") else result["is_valid"]


@then("the validation should fail")
def validation_fail(context):
    result = context["validation_result"]
    assert not (result.is_valid if hasattr(result, "is_valid") else result["is_valid"])


@then("there should be no errors")
def no_errors(context):
    errors = context.get("validation_errors") or (
        context["validation_result"].errors
        if hasattr(context["validation_result"], "errors")
        else context["validation_result"]["errors"]
    )
    assert not errors


@then("I should get an error about invalid dimensions")
def error_invalid_dimensions(context):
    errors = " ".join(context.get("validation_errors", [])).lower()
    assert any(
        token in errors
        for token in (
            "dimension",
            "length",
            "width",
            "height",
            "thickness",
            "greater than",
            "equal to",
        )
    )


@then("I should get an error about weight exceeding maximum")
def error_weight_or_resolution_weight(context):
    if context.get("resolution_error") is not None:
        assert context["resolution_error"].code == PortoErrorCode.PORTO_TOO_HEAVY
        return
    errors = " ".join(context.get("validation_errors", [])).lower()
    assert "weight" in errors or "heavy" in errors or "tier" in errors


@then("I should get an error about invalid address")
def error_invalid_address(context):
    errors = " ".join(context.get("validation_errors", [])).lower()
    assert any(token in errors for token in ("address", "postal", "street", "character", "pattern"))


@then("I should get errors about missing required fields")
def errors_missing_fields(context):
    assert context.get("validation_errors")


@then("I should get an error about invalid country code")
def error_invalid_country(context):
    if context.get("resolution_error") is not None:
        assert context["resolution_error"].code == PortoErrorCode.PORTO_DESTINATION_INVALID
        return
    errors = " ".join(context.get("validation_errors", [])).lower()
    assert "country" in errors
