"""Step definitions for metadata.feature (postal catalog + envelope matching)."""

from pytest_bdd import given, parsers, then, when


@given(parsers.parse('I have a Porto SDK client initialized for provider "{provider_id}"'))
def client_for_provider(client, context, provider_id: str):
    from porto_sdk import PortoClient
    from porto_sdk.config import PortoConfig, ProviderRuntimeConfig
    from tests.support.porto_features_path import get_porto_data_path

    context["client"] = PortoClient(
        PortoConfig(
            providers={provider_id: ProviderRuntimeConfig()},
            data=get_porto_data_path(),
        )
    )
    context["provider_id"] = provider_id


@when("I list postal providers")
def list_postal_providers(context):
    context["providers"] = context["client"].providers.list()


@then(parsers.parse('the providers list should contain provider id "{provider_id}"'))
def providers_contain(provider_id: str, context):
    ids = {p.id for p in context["providers"]}
    assert provider_id in ids


@when(parsers.parse('I list products for provider "{provider_id}"'))
def list_products_for_provider(context, provider_id: str):
    from tests.bdd.steps.helpers import PROVIDER_HOME_COUNTRY

    home = PROVIDER_HOME_COUNTRY.get(provider_id, "DE")
    context["products"] = (
        context["client"]
        .provider(provider_id)
        .options(
            country_code=home,
            weight=20,
        )
    )


@then(parsers.parse('the products list should contain product id "{product_id}"'))
def products_contain(product_id: str, context):
    ids = {p.id for p in context["products"]}
    assert product_id in ids


@when("I list envelope catalog")
def list_envelope_catalog(context):
    context["envelopes"] = context["client"].envelopes.list()


@when(parsers.parse('I list envelopes for provider "{provider_id}"'))
def list_envelopes_for_provider(context, provider_id: str):
    del provider_id
    list_envelope_catalog(context)


@then(parsers.parse('the envelopes list should contain envelope id "{envelope_id}"'))
def envelopes_contain(envelope_id: str, context):
    def _env_id(item):
        return item.id if hasattr(item, "id") else item["id"]

    ids = {_env_id(e) for e in context["envelopes"]}
    assert envelope_id in ids


@when(parsers.parse('I get envelope geometry for id "{envelope_id}" jurisdiction "{jurisdiction}"'))
def get_envelope_geometry(context, envelope_id: str, jurisdiction: str):
    context["geometry"] = context["client"].envelopes.geometry(envelope_id, jurisdiction)


@then(parsers.parse("the envelope width should be {width:d} mm"))
def envelope_width(width: int, context):
    geometry = context["geometry"]
    assert geometry["width"] == width


@then(parsers.parse("the envelope height should be {height:d} mm"))
def envelope_height(height: int, context):
    geometry = context["geometry"]
    assert geometry["height"] == height


@when(parsers.parse('I validate envelope "{envelope_id}" for product "{product_id}"'))
def validate_envelope_for_product(context, envelope_id: str, product_id: str):
    context["match"] = context["client"].envelopes.validate_for_product(envelope_id, product_id)


@when(parsers.parse('I resolve envelope "{envelope_id}" for product "{product_id}"'))
def resolve_envelope_for_product(context, envelope_id: str, product_id: str):
    context["match"] = context["client"].envelopes.resolve(
        {"kind": "by_id", "envelope_id": envelope_id},
        product_id,
    )


@then(parsers.parse('the match kind should be "{kind}"'))
def match_kind(kind: str, context):
    assert context["match"].kind == kind


@then(parsers.parse('the match envelope id should be "{envelope_id}"'))
def match_envelope_id(envelope_id: str, context):
    assert context["match"].envelope_id == envelope_id


@then(parsers.parse("the match should have advisory_only {value}"))
def match_advisory_only(value: str, context):
    expected = value.lower() == "true"
    assert context["match"].advisory_only is expected


@then(parsers.parse('the match reason should be "{reason}"'))
def match_reason(reason: str, context):
    assert context["match"].reason == reason
