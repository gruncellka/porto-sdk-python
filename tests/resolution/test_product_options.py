"""Product options expose catalog facts — not inferred labels."""

from __future__ import annotations

import pytest

from tests.support.bound_provider import bound_provider


@pytest.mark.offline
def test_options_use_country_code_and_catalog_facts(client) -> None:
    bound = bound_provider(client)
    rows = bound.options(country_code="DE", weight=20, envelope_id="DL")
    ids = {row.id for row in rows}
    assert "standardbrief" in ids
    chosen = next(row for row in rows if row.id == "standardbrief")
    porto = bound.resolve(
        country_code="DE",
        weight=20,
        envelope_id="DL",
        product_id=chosen.id,
    )
    assert porto.amount == chosen.amount
    assert porto.currency == chosen.currency


@pytest.mark.offline
def test_options_include_priced_service_options_for_product(client) -> None:
    bound = bound_provider(client)
    rows = bound.options(country_code="DE", weight=20, envelope_id="DL")
    chosen = next(row for row in rows if row.id == "standardbrief")
    service_ids = {svc.id for svc in chosen.services}
    assert "einschreiben" in service_ids
    assert "einschreiben_rueckschein" in service_ids
    einschreiben = next(svc for svc in chosen.services if svc.id == "einschreiben")
    assert einschreiben.kind == "registered"
    assert einschreiben.amount is not None and einschreiben.amount > 0
    assert einschreiben.currency == "EUR"


@pytest.mark.offline
def test_options_pin_ambiguous_registered_from_discovered_service_id(client) -> None:
    bound = bound_provider(client)
    rows = bound.options(country_code="DE", weight=20, envelope_id="DL")
    chosen = next(row for row in rows if row.id == "standardbrief")
    pin = next(svc for svc in chosen.services if svc.kind == "registered" and svc.id == "einschreiben")
    porto = bound.resolve(
        country_code="DE",
        weight=20,
        envelope_id="DL",
        product_id=chosen.id,
        services=["registered"],
        service_ids=[pin.id],
    )
    assert porto.is_valid
    assert "einschreiben" in porto.service_ids
    assert porto.amount == (chosen.amount or 0) + (pin.amount or 0)


@pytest.mark.offline
def test_options_scopes_service_lists_per_product(client) -> None:
    bound = bound_provider(client, "swisspost")
    rows = bound.options(country_code="CH", weight=20)
    assert len(rows) > 1
    for row in rows:
        assert isinstance(row.services, list)
        assert len(row.services) > 0
        assert all(svc.id and svc.currency == "CHF" for svc in row.services)
    left, right = rows[0], rows[1]
    # Each ProductOption carries its own list (product × zone), not a shared global bag.
    assert left.services is not right.services


@pytest.mark.offline
def test_price_matches_resolved_porto_without_being_required(client) -> None:
    bound = bound_provider(client)
    porto = bound.resolve(
        country_code="DE",
        weight=20,
        envelope_id="DL",
        product_id="standardbrief",
    )
    pricing = bound.price(
        country_code="DE",
        weight=20,
        envelope_id="DL",
        product_id="standardbrief",
    )
    assert pricing.amount == porto.amount
    assert pricing.currency == porto.currency
    assert pricing.product_id == porto.product.id
