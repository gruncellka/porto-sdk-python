"""Tests for ResolutionIndex and service_prices loading."""

from __future__ import annotations

import pytest

from porto_sdk import PortoClient, PortoConfig
from porto_sdk.config import ProviderRuntimeConfig
from porto_sdk.data.loader import PortoDataLoader
from tests.support.bound_provider import bound_provider
from tests.support.porto_features_path import get_porto_data_path


@pytest.mark.offline
def test_resolution_index_de_standardbrief_domestic():
    loader = PortoDataLoader(
        get_porto_data_path(),
        provider="deutschepost",
        verify_checksums=False,
        strict_mode=False,
    )
    assert loader.resolution_index is not None
    ids = loader.resolution_index.candidates("domestic", "W0020")
    assert "standardbrief" in ids


@pytest.mark.offline
def test_service_prices_loaded_for_deutschepost():
    loader = PortoDataLoader(
        get_porto_data_path(),
        provider="deutschepost",
        verify_checksums=False,
        strict_mode=False,
    )
    assert loader.get_service_price("einschreiben") is None
    assert loader.get_service_price("einschreiben", "domestic") == 265
    assert loader.get_service_price("einschreiben", "world") == 370
    assert loader.get_service_price("einschreiben", "zone_1_eu") == 370
    assert loader.get_service_price("einschreiben", "zone_2_europe") == 370
    assert loader.get_service_price("einschreiben_einwurf") == 235


@pytest.mark.offline
def test_resolver_reads_catalog_einschreiben_by_zone():
    client = PortoClient(
        PortoConfig(
            providers={"deutschepost": ProviderRuntimeConfig()},
            data=get_porto_data_path(),
            strict_data_validation=False,
        )
    )
    resolver = bound_provider(client)._resolver
    assert resolver.get_service_price("einschreiben") is None
    assert resolver.get_service_price("einschreiben", "domestic") == 265
    assert resolver.get_service_price("einschreiben", "world") == 370
    assert resolver.get_service_price("einschreiben", "zone_1_eu") == 370
    assert resolver.get_service_price("einschreiben", "zone_2_europe") == 370
    assert resolver.get_service_price("einschreiben_einwurf") == 235


@pytest.mark.offline
def test_resolution_index_build_from_graph():
    loader = PortoDataLoader(
        get_porto_data_path(),
        provider="laposte",
        verify_checksums=False,
        strict_mode=False,
    )
    index = loader.resolution_index
    assert index is not None
    assert index.has_graph_edge("lettre_verte")


@pytest.mark.offline
def test_price_overweight_is_too_heavy():
    from porto_sdk.errors import PortoError, PortoErrorCode

    client = PortoClient(
        PortoConfig(
            providers={"deutschepost": ProviderRuntimeConfig()},
            data=get_porto_data_path(),
            strict_data_validation=False,
        )
    )
    with pytest.raises(PortoError) as exc:
        bound_provider(client).price(
            product_id="standardbrief",
            country_code="DE",
            weight=50000,
        )
    assert exc.value.code == PortoErrorCode.PORTO_TOO_HEAVY
