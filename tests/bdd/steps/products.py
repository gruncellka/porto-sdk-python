"""Step definitions for product_options.feature."""

from pytest_bdd import given, parsers, then, when

from tests.support.bound_provider import bound_provider


@given(parsers.parse('envelope id is "{envelope_id}"'))
def set_envelope_id(envelope_id, context):
    context["envelope_id"] = envelope_id


@when("I list product options")
def list_product_options_step(context):
    client = context["client"]
    options = bound_provider(client, context.get("provider_id", "deutschepost")).options(
        country_code=context.get("destination_country", "DE"),
        weight=context.get("letter_weight", 20),
        envelope_id=context.get("envelope_id"),
    )
    context["product_options"] = options


def _option_by_id(context, product_id: str):
    options = context.get("product_options") or []
    for row in options:
        if row.id == product_id:
            return row
    return None


@then(parsers.parse('product options should include "{product_id}"'))
def product_options_include(product_id, context):
    assert _option_by_id(context, product_id) is not None


@then(parsers.parse('product options should not include "{product_id}"'))
def product_options_exclude(product_id, context):
    assert _option_by_id(context, product_id) is None


@then(parsers.parse('product option "{product_id}" should have a price'))
def product_option_has_price(product_id, context):
    row = _option_by_id(context, product_id)
    assert row is not None
    assert row.amount is not None
    assert row.amount > 0


@then(parsers.parse('product option "{product_id}" should include service "{service_id}"'))
def product_option_includes_service(product_id, service_id, context):
    row = _option_by_id(context, product_id)
    assert row is not None
    assert any(svc.id == service_id for svc in row.services)


@when(
    parsers.parse(
        'I resolve using product "{product_id}" and discovered service "{service_id}"'
    )
)
def resolve_using_discovered_service(product_id, service_id, context):
    from tests.bdd.steps.helpers import public_resolve

    row = _option_by_id(context, product_id)
    assert row is not None
    svc = next((item for item in row.services if item.id == service_id), None)
    assert svc is not None
    assert svc.kind is not None
    context["product_id"] = product_id
    context["services_kinds"] = [svc.kind]
    context["service_ids"] = [svc.id]
    try:
        context["resolved"] = public_resolve(context)
        context["resolution_error"] = None
    except Exception as exc:  # noqa: BLE001 — BDD captures SDK errors
        context["resolved"] = None
        context["resolution_error"] = exc


@then("I should get a non-empty list of product options")
def product_options_non_empty(context):
    options = context.get("product_options") or []
    assert len(options) > 0
