"""
Multi-provider SDK tests - ONE resolver, provider-native outputs, no provider branching.
"""

import inspect

import pytest

from porto_sdk import PortoClient
from porto_sdk.config import DEFAULT_PROVIDER, CacheConfig, PortoConfig, ProviderRuntimeConfig
from porto_sdk.data.context import PostalResolutionContext
from porto_sdk.data.domain_validator import DomainIds
from porto_sdk.data.loader import PortoDataLoader
from porto_sdk.data.porto_data_registry import get_valid_providers_from_mappings
from porto_sdk.services.porto_resolver import PortoResolver, ResolutionRequest
from tests.support.bound_provider import bound_provider


class TestProviderConfig:
    def test_default_provider(self):
        cfg = PortoConfig(data="/tmp")
        assert cfg.normalize().default_provider == DEFAULT_PROVIDER

    def test_provider_deutschepost(self, porto_data_path):
        cfg = PortoConfig(
            providers={"deutschepost": ProviderRuntimeConfig()},
            data=porto_data_path,
            strict_data_validation=False,
        )
        assert cfg.normalize().default_provider == "deutschepost"

    def test_provider_swisspost(self, porto_data_path):
        cfg = PortoConfig(providers={"swisspost": ProviderRuntimeConfig()}, data=porto_data_path)
        assert cfg.normalize().default_provider == "swisspost"

    def test_provider_case_insensitive(self, porto_data_path):
        cfg = PortoConfig(providers={"DeutschePost": ProviderRuntimeConfig()}, data=porto_data_path)
        assert cfg.normalize().default_provider.lower() == "deutschepost"

    def test_invalid_provider_raises(self, porto_data_path):
        with pytest.raises(ValueError, match="Invalid provider"):
            PortoConfig(providers={"invalid": ProviderRuntimeConfig()}, data=porto_data_path)

    def test_valid_providers_from_porto_data(self, porto_data_path):
        valid = get_valid_providers_from_mappings(porto_data_path)
        assert "deutschepost" in valid
        assert "swisspost" in valid


class TestMultiProviderLoading:
    def test_load_deutschepost_products(self, porto_data_path):
        loader = PortoDataLoader(
            porto_data_path,
            provider="deutschepost",
            verify_checksums=False,
            strict_mode=False,
        )
        products = loader.get_all_products()
        ids = [p.id for p in products]
        assert "standardbrief" in ids
        assert "kompaktbrief" in ids
        assert "grossbrief" in ids
        assert "maxibrief" in ids

    def test_load_swisspost_products(self, porto_data_path):
        loader = PortoDataLoader(
            porto_data_path,
            provider="swisspost",
            verify_checksums=False,
            strict_mode=False,
        )
        products = loader.get_all_products()
        ids = [p.id for p in products]
        assert "a_post_standardbrief" in ids
        assert "b_post_standardbrief" in ids
        assert "standardbrief" not in ids


class TestPortoResolver:
    @pytest.fixture
    def resolver_deutschepost(self, porto_data_path):
        loader = PortoDataLoader(
            porto_data_path,
            provider="deutschepost",
            verify_checksums=False,
            strict_mode=False,
        )
        validator = DomainIds(loader)
        ctx = PostalResolutionContext(loader=loader, provider_id="deutschepost")
        return PortoResolver(ctx, validator, CacheConfig(enabled=False))

    @pytest.fixture
    def resolver_swisspost(self, porto_data_path):
        loader = PortoDataLoader(
            porto_data_path,
            provider="swisspost",
            verify_checksums=False,
            strict_mode=False,
        )
        validator = DomainIds(loader)
        ctx = PostalResolutionContext(loader=loader, provider_id="swisspost")
        return PortoResolver(ctx, validator, CacheConfig(enabled=False))

    def test_deutschepost_returns_provider_native_product(self, resolver_deutschepost):
        resolved = resolver_deutschepost.resolve(
            ResolutionRequest(
                country_code="DE",
                weight=20,
            )
        )
        assert resolved.product.id == "standardbrief"
        assert resolved.product.name == "Standardbrief"
        assert resolved.delivery_hint is not None

    def test_swisspost_returns_provider_native_product(self, resolver_swisspost):
        resolved = resolver_swisspost.resolve(
            ResolutionRequest(
                country_code="CH",
                weight=20,
                delivery_preference="cheapest",
            )
        )
        assert resolved.product.id in ("a_post_standardbrief", "b_post_standardbrief")

    def test_deutschepost_currency_eur(self, resolver_deutschepost):
        resolved = resolver_deutschepost.resolve(ResolutionRequest(country_code="DE", weight=20))
        assert resolved.currency == "EUR"

    def test_deutschepost_maxibrief_domestic_resolves(self, resolver_deutschepost):
        resolved = resolver_deutschepost.resolve(
            ResolutionRequest(
                country_code="DE",
                weight=501,
            )
        )
        assert resolved.product.id == "maxibrief"
        assert resolved.zone.id == "domestic"
        assert resolved.weight_tier.id == "W1000"

    def test_deutschepost_maxibrief_international_w1000_resolves(self, resolver_deutschepost):
        resolved = resolver_deutschepost.resolve(
            ResolutionRequest(
                country_code="FR",
                weight=501,
            )
        )
        assert resolved.product.id == "maxibrief"
        assert resolved.zone.id == "zone_1_eu"

    def test_deutschepost_maxibrief_ausland_international_w2000_resolves(
        self, resolver_deutschepost
    ):
        resolved = resolver_deutschepost.resolve(
            ResolutionRequest(
                country_code="FR",
                weight=1001,
            )
        )
        assert resolved.product.id == "maxibrief_ausland"
        assert resolved.zone.id == "zone_1_eu"
        assert resolved.weight_tier.id == "W2000"

    def test_swisspost_currency_chf(self, resolver_swisspost):
        resolved = resolver_swisspost.resolve(ResolutionRequest(country_code="CH", weight=20))
        assert resolved.currency == "CHF"


class TestClientOutputContract:
    def test_resolve_returns_provider_in_output(self, porto_data_path):
        cfg = PortoConfig(
            providers={"deutschepost": ProviderRuntimeConfig()},
            data=porto_data_path,
            strict_data_validation=False,
        )
        client = PortoClient(cfg)
        result = bound_provider(client).resolve(country_code="DE", weight=20)
        assert result.product.id == "standardbrief"
        assert result.delivery_hint is not None

    @pytest.mark.asyncio
    async def test_envelopes_identify_returns_format(self, porto_data_path):
        cfg = PortoConfig(
            providers={"deutschepost": ProviderRuntimeConfig()},
            data=porto_data_path,
            strict_data_validation=False,
        )
        client = PortoClient(cfg)
        result = await client.envelopes.identify(envelope_format="DL", weight=20)
        assert result.format == "DL"


class TestNoProviderBranching:
    def test_resolver_has_no_provider_branches(self):
        source = inspect.getsource(PortoResolver)
        forbidden = [
            '== "deutschepost"',
            '== "swisspost"',
            '== "DeutschePost"',
            '== "SwissPost"',
        ]
        for pattern in forbidden:
            assert pattern not in source, (
                f"Resolver must not contain provider branching: {pattern!r}"
            )
