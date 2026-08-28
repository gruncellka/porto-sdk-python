"""Service kind vs catalog id bind — 0.1.0 freeze."""

from __future__ import annotations

import pytest

from porto_sdk import PortoClient
from porto_sdk.config import PortoConfig, ProviderRuntimeConfig
from porto_sdk.errors import PortoError, PortoErrorCode
from tests.support.bound_provider import bound_provider


@pytest.mark.offline
def test_registered_without_pin_is_ambiguous(client) -> None:
    with pytest.raises(PortoError) as exc:
        bound_provider(client).resolve(country_code="DE", weight=20, services=["registered"])
    assert exc.value.code == PortoErrorCode.PORTO_SERVICE_AMBIGUOUS
    assert exc.value.details["kind"] == "registered"
    ids = {row["id"] for row in exc.value.details["candidates"]}
    assert "einschreiben" in ids
    assert "einschreiben_einwurf" in ids


@pytest.mark.offline
def test_registered_pin_selects_catalog_id(client) -> None:
    porto = bound_provider(client).resolve(
        country_code="DE",
        weight=20,
        services=["registered"],
        service_ids=["einschreiben"],
    )
    assert porto.services == ("registered",)
    assert porto.service_ids == ("einschreiben",)
    assert any(row.id == "einschreiben" for row in porto.available_services)
    assert all(hasattr(row, "kind") for row in porto.available_services)
    assert all(hasattr(row, "kind") for row in porto.features)


@pytest.mark.offline
def test_service_ids_kind_string_is_invalid(client) -> None:
    with pytest.raises(PortoError) as exc:
        bound_provider(client).resolve(
            country_code="DE",
            weight=20,
            services=["registered"],
            service_ids=["registered"],
        )
    assert exc.value.code == PortoErrorCode.PORTO_DATA_INVALID


@pytest.mark.offline
def test_can_feature_kind_not_catalog_id(client) -> None:
    bound = bound_provider(client)
    assert bound.can("tracking") is True
    assert bound.can("sendungsnummer") is False
    assert bound.can("not_a_kind") is False


@pytest.mark.offline
def test_explicit_kind_with_no_catalog_or_product_match_is_unsupported(client) -> None:
    with pytest.raises(PortoError) as exc:
        bound_provider(client).resolve(country_code="DE", weight=20, services=["thickness"])
    assert exc.value.code == PortoErrorCode.PORTO_SERVICE_UNSUPPORTED
    assert exc.value.details["kind"] == "thickness"


@pytest.mark.offline
def test_laposte_registered_kind_matches_product_capability(porto_data_path) -> None:
    client = PortoClient(
        PortoConfig(data=porto_data_path, providers={"laposte": ProviderRuntimeConfig()})
    )
    porto = bound_provider(client, "laposte").resolve(
        country_code="FR",
        weight=20,
        services=["registered"],
        indemnity_tier="R1",
    )
    assert porto.services == ("registered",)
    assert porto.product.indemnity is not None
    assert porto.product.indemnity.tier == "R1"
