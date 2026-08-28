"""PortoClient.clear_cache clears shared per-provider resolvers."""

from __future__ import annotations

import pytest

from porto_sdk import PortoClient, PortoConfig
from porto_sdk.config import CacheConfig
from porto_sdk.services.porto_resolver import ResolutionRequest


@pytest.mark.offline
def test_clear_cache_clears_all_shared_resolvers(porto_data_path: str) -> None:
    client = PortoClient(
        PortoConfig(
            data=porto_data_path,
            providers={"deutschepost": {}, "swisspost": {}},
            cache=CacheConfig(enabled=True, ttl=3600, max_size=128),
        )
    )
    de = client.provider("deutschepost")
    ch = client.provider("swisspost")

    assert de._resolver is client._resolver_for("deutschepost", de._data_loader)
    assert ch._resolver is client._resolver_for("swisspost", ch._data_loader)
    assert de._resolver is not ch._resolver

    de._resolver.resolve(ResolutionRequest(country_code="DE", weight=20))
    ch._resolver.resolve(ResolutionRequest(country_code="CH", weight=20))
    assert de._resolver.get_cache_stats()["size"] >= 1
    assert ch._resolver.get_cache_stats()["size"] >= 1

    client.clear_cache()

    assert de._resolver.get_cache_stats()["size"] == 0
    assert ch._resolver.get_cache_stats()["size"] == 0
