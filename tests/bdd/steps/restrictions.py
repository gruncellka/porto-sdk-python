"""Step definitions for restrictions.feature."""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.bdd.steps.helpers import provider_id_from_context
from tests.support.addresses import load_address_fixture


def _lookup(context):
    client = context["client"]
    provider_id = provider_id_from_context(context)
    country = context.get("destination_country", "DE")
    region = context.get("destination_region")
    return client.provider(provider_id).restrictions.check(country, region)


def _legal_items(result):
    return list(result.legal)


def _routing_items(result):
    return list(result.routing)


def _jurisdiction_blob(result) -> str:
    parts: list[str] = []
    for item in _legal_items(result):
        for row in item.jurisdictions:
            if row.reference:
                parts.append(row.reference)
            parts.append(row.jurisdiction)
    return " ".join(parts)


@when("I check destination restrictions")
def when_resolve_destination_restrictions(context):
    context["restriction_result"] = _lookup(context)


@then(parsers.parse('the restriction result impact should be "{impact}"'))
def restriction_impact(impact: str, context):
    assert context["restriction_result"].impact == impact


@then("the restriction result impact should be null")
def restriction_impact_null(context):
    assert context["restriction_result"].impact is None


@then("the restriction result list should be empty")
def restriction_list_empty(context):
    assert context["restriction_result"].legal == ()
    assert context["restriction_result"].routing == ()


@then(parsers.parse('the restriction result should include legal region "{region_code}"'))
def restriction_legal_region(region_code: str, context):
    assert any(item.region_code == region_code for item in _legal_items(context["restriction_result"]))


@then(parsers.parse('the restriction result should not include legal region "{region_code}"'))
def restriction_legal_region_absent(region_code: str, context):
    assert all(item.region_code != region_code for item in _legal_items(context["restriction_result"]))


@then(parsers.parse('the restriction result legal region "{region_code}" should be partial'))
def restriction_legal_region_partial(region_code: str, context):
    matches = [item for item in _legal_items(context["restriction_result"]) if item.region_code == region_code]
    assert matches and all(item.partial for item in matches)


@then(parsers.parse('the restriction result legal jurisdictions should include "{token}"'))
def restriction_legal_jurisdictions_include(token: str, context):
    assert token in _jurisdiction_blob(context["restriction_result"])


@then(parsers.parse('the restriction result legal jurisdictions should not include "{token}"'))
def restriction_legal_jurisdictions_exclude(token: str, context):
    assert token not in _jurisdiction_blob(context["restriction_result"])


@then(parsers.parse('the restriction result should include routing region "{region_code}"'))
def restriction_routing_region(region_code: str, context):
    assert any(item.region_code == region_code for item in _routing_items(context["restriction_result"]))


@then(parsers.parse('the restriction result routing authority should be "{authority}"'))
def restriction_routing_authority(authority: str, context):
    assert any(item.authority == authority for item in _routing_items(context["restriction_result"]))


@then(parsers.parse('the restriction result routing region "{region_code}" should be partial'))
def restriction_routing_region_partial(region_code: str, context):
    matches = [
        item for item in _routing_items(context["restriction_result"]) if item.region_code == region_code
    ]
    assert matches and all(item.partial for item in matches)


@then("the resolved Porto restrictions should have no impact")
def resolved_no_impact(context):
    assert context["resolved"].restrictions.impact is None


@then("the resolved Porto restrictions list should be empty")
def resolved_list_empty(context):
    assert context["resolved"].restrictions.legal == ()
    assert context["resolved"].restrictions.routing == ()


@then("the resolved Porto restrictions should match standalone restriction lookup")
def resolved_restrictions_match_lookup(context):
    standalone = _lookup(context)
    assert context["resolved"].restrictions == standalone


@given("I want to send a letter to a restricted country")
def restricted_country(context):
    context["destination_country"] = "UA"
    context["destination_region"] = "UA-14"


@given(parsers.parse('I have destination address fixture "{fixture_id}"'))
def destination_fixture(fixture_id: str, context):
    address = load_address_fixture(fixture_id)
    context["destination_address"] = address
    context["address"] = address


@given(parsers.parse('destination region code is "{region_code}"'))
def destination_region(region_code: str, context):
    context["destination_region"] = region_code


@given("the destination country has restrictions")
def destination_has_restrictions(context):
    context["destination_country"] = "UA"


@given("valid dimensions and weight")
def valid_dimensions_and_weight(context):
    context.setdefault("letter_length", 210)
    context.setdefault("letter_width", 148)
    context.setdefault("letter_height", 5)
    context.setdefault("weight", 20)
    context.setdefault("letter_weight", 20)


@then("I should get warnings about restrictions")
def warnings_about_restrictions(context):
    warnings = context.get("validation_warnings", [])
    assert warnings


@then("the warnings should include restriction details")
def warnings_include_details(context):
    warnings = context.get("validation_warnings", [])
    assert any("restrict" in warning.lower() for warning in warnings)
