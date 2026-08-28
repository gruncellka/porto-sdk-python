"""Step definitions for data.feature — public catalog surfaces."""

from __future__ import annotations

from pytest_bdd import parsers, then, when


@when("I inspect envelopes data")
def access_envelopes(context):
    context["envelopes"] = context["client"].envelopes.list()


@when("I inspect the provider registry")
def access_provider_registry(context):
    context["providers_data"] = {
        "providers": [
            {"id": provider.id, "name": provider.name, "country": provider.country}
            for provider in context["client"].providers.list()
        ]
    }


@when(parsers.parse('I look up country code 3 for "{country_code}"'))
def look_up_country_code_3(country_code: str, context):
    context["country_code_3"] = context["client"].jurisdictions.country_code_3(country_code)


@then("I should get providers information")
def should_get_providers_information(context):
    assert isinstance(context.get("providers_data"), dict)


@then(parsers.parse('the country code 3 should be "{country_code_3}"'))
def country_code_3_should_be(country_code_3: str, context):
    assert context.get("country_code_3") == country_code_3
