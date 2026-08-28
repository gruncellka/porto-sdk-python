"""Integration tests for delivery_hint resolution against porto-data."""

import pytest

from porto_sdk import PortoClient
from porto_sdk.config import CacheConfig, PortoConfig, ProviderRuntimeConfig
from porto_sdk.data.context import PostalResolutionContext
from porto_sdk.data.domain_validator import DomainIds
from porto_sdk.data.loader import PortoDataLoader
from porto_sdk.errors import PortoError, PortoErrorCode
from porto_sdk.services.porto_resolver import PortoResolver, ResolutionRequest
from tests.support.bound_provider import bound_provider


def _resolver(porto_data_path: str, provider: str) -> PortoResolver:
    loader = PortoDataLoader(
        porto_data_path,
        provider=provider,
        verify_checksums=False,
        strict_mode=False,
    )
    validator = DomainIds(loader)
    ctx = PostalResolutionContext(loader=loader, provider_id=provider)
    return PortoResolver(ctx, validator, CacheConfig(enabled=False))


@pytest.mark.offline
class TestDeliveryResolutionIntegration:
    def test_deutschepost_domestic_delivery_hint(self, porto_data_path):
        resolved = _resolver(porto_data_path, "deutschepost").resolve(
            ResolutionRequest(
                country_code="DE",
                weight=20,
            )
        )
        assert resolved.product.id == "standardbrief"
        assert resolved.delivery_hint is not None
        assert resolved.delivery_hint.span == "between"
        assert resolved.delivery_hint.days_min == 1
        assert resolved.delivery_hint.days_max == 2
        assert resolved.delivery_hint.working_days.weekdays == "mon_sat"
        assert resolved.delivery_hint.working_days.market == "DE"

    def test_deutschepost_international_delivery_hint(self, porto_data_path):
        resolved = _resolver(porto_data_path, "deutschepost").resolve(
            ResolutionRequest(
                country_code="US",
                weight=20,
            )
        )
        assert resolved.delivery_hint is not None
        assert resolved.delivery_hint.days_max == 12
        assert resolved.delivery_hint.working_days.market == "DE"

    def test_laposte_economy_explicit_product(self, porto_data_path):
        resolved = _resolver(porto_data_path, "laposte").resolve(
            ResolutionRequest(
                country_code="FR",
                weight=20,
                product_id="lettre_verte",
            )
        )
        assert resolved.product.id == "lettre_verte"
        assert resolved.delivery_hint.span == "within"
        assert resolved.delivery_hint.days_max == 3
        assert resolved.delivery_hint.working_days.weekdays == "mon_fri"

    def test_laposte_fast_explicit_product(self, porto_data_path):
        resolved = _resolver(porto_data_path, "laposte").resolve(
            ResolutionRequest(
                country_code="FR",
                weight=20,
                product_id="lettre_services_plus",
            )
        )
        assert resolved.product.id == "lettre_services_plus"
        assert resolved.delivery_hint.span == "between"
        assert resolved.delivery_hint.days_min == 1
        assert resolved.delivery_hint.days_max == 2

    def test_laposte_ambiguous_without_hint(self, porto_data_path):
        with pytest.raises(PortoError) as exc:
            _resolver(porto_data_path, "laposte").resolve(
                ResolutionRequest(
                    country_code="FR",
                    weight=20,
                )
            )
        assert exc.value.code == PortoErrorCode.PORTO_PRODUCT_AMBIGUOUS

    def test_laposte_fastest_preference(self, porto_data_path):
        resolved = _resolver(porto_data_path, "laposte").resolve(
            ResolutionRequest(
                country_code="FR",
                weight=20,
                delivery_preference="fastest",
            )
        )
        assert resolved.product.id == "lettre_services_plus"

    def test_swisspost_fastest_preference(self, porto_data_path):
        resolved = _resolver(porto_data_path, "swisspost").resolve(
            ResolutionRequest(
                country_code="CH",
                weight=20,
                delivery_preference="fastest",
            )
        )
        assert resolved.product.id == "a_post_standardbrief"

    def test_swisspost_economy_preference(self, porto_data_path):
        resolved = _resolver(porto_data_path, "swisspost").resolve(
            ResolutionRequest(
                country_code="CH",
                weight=20,
                delivery_preference="economy",
            )
        )
        assert resolved.product.id == "b_post_standardbrief"

    def test_client_resolve_includes_delivery_hint(self, porto_data_path):
        client = PortoClient(
            PortoConfig(
                providers={"deutschepost": ProviderRuntimeConfig()},
                data=porto_data_path,
                strict_data_validation=False,
            )
        )
        result = bound_provider(client).resolve(
            country_code="DE",
            weight=20,
        )
        assert result.delivery_hint is not None
        assert result.delivery_hint.days_max == 2
        assert result.product.id == "standardbrief"

    def test_markets_loader_all_providers(self, porto_data_path):
        expected = {
            "deutschepost": ("DE", "mon_sat"),
            "laposte": ("FR", "mon_fri"),
            "swisspost": ("CH", "mon_sat"),
            "ukrposhta": ("UA", "mon_fri"),
        }
        for provider, (country, weekdays) in expected.items():
            loader = PortoDataLoader(
                porto_data_path,
                provider=provider,
                verify_checksums=False,
                strict_mode=False,
            )
            market = loader.get_market(country)
            assert market is not None
            assert market.working_days.weekdays == weekdays
