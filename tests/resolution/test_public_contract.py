"""0.1.0 public ProviderClient contract (unit layer).

Mirrors core BDD invariants through public ``resolve()``, ``price()``, and
``restrictions.check()`` — no private resolver access in this module.
"""

from __future__ import annotations

import pytest

from porto_sdk.errors import PortoError, PortoErrorCode
from tests.support.bound_provider import bound_provider


@pytest.mark.offline
class TestResolveHappyPath:
    def test_resolve_without_product_pin(self, client) -> None:
        porto = bound_provider(client).resolve(country_code="DE", weight=20)
        assert porto.is_valid is True
        assert porto.product.id
        assert porto.amount > 0
        assert porto.currency == "EUR"
        assert porto.restrictions is not None

    def test_optional_product_pin(self, client) -> None:
        porto = bound_provider(client).resolve(
            country_code="DE",
            weight=20,
            product_id="standardbrief",
        )
        assert porto.product.id == "standardbrief"
        assert porto.amount > 0


@pytest.mark.offline
class TestQuoteParity:
    def test_price_amount_equals_resolve_amount(self, client) -> None:
        bound = bound_provider(client)
        porto = bound.resolve(country_code="DE", weight=20)
        pricing = bound.price(country_code="DE", weight=20)
        assert pricing.amount == porto.amount
        assert pricing.currency == porto.currency

    def test_components_sum_to_amount_for_bound_service(self, client) -> None:
        bound = bound_provider(client)
        porto = bound.resolve(
            country_code="DE",
            weight=20,
            services=["registered_return_receipt"],
        )
        assert sum(row.amount for row in porto.components) == porto.amount
        assert porto.amount > 0


@pytest.mark.offline
class TestServiceKindBinding:
    def test_unique_kind_binds_without_catalog_pin(self, client) -> None:
        porto = bound_provider(client).resolve(
            country_code="DE",
            weight=20,
            services=["registered_return_receipt"],
        )
        assert "registered_return_receipt" in porto.services
        assert "einschreiben_rueckschein" in porto.service_ids

    def test_ambiguous_kind_fails_closed(self, client) -> None:
        with pytest.raises(PortoError) as exc:
            bound_provider(client).resolve(
                country_code="DE",
                weight=20,
                services=["registered"],
            )
        assert exc.value.code == PortoErrorCode.PORTO_SERVICE_AMBIGUOUS

    def test_unsupported_kind_fails_closed(self, client) -> None:
        with pytest.raises(PortoError) as exc:
            bound_provider(client).resolve(
                country_code="DE",
                weight=20,
                services=["thickness"],
            )
        assert exc.value.code == PortoErrorCode.PORTO_SERVICE_UNSUPPORTED

    def test_incompatible_service_pins_fail_closed(self, client) -> None:
        with pytest.raises(PortoError) as exc:
            bound_provider(client).resolve(
                country_code="DE",
                weight=20,
                services=["registered"],
                service_ids=["einschreiben", "einschreiben_einwurf"],
            )
        assert exc.value.code == PortoErrorCode.PORTO_SERVICES_INCOMPATIBLE


@pytest.mark.offline
class TestPriceZoneDerivation:
    def test_price_derives_zone_from_country_code(self, client) -> None:
        bound = bound_provider(client)
        domestic = bound.price(country_code="DE", weight=20)
        eu = bound.price(country_code="FR", weight=20)
        world = bound.price(country_code="US", weight=20)
        assert domestic.zone_id == "domestic"
        assert eu.zone_id == "zone_1_eu"
        assert world.zone_id == "world"
        assert domestic.amount > 0
        assert eu.amount > domestic.amount
        assert world.amount > domestic.amount
