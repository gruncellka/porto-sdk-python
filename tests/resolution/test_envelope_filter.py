"""Envelope is a physical fit filter — not a product selector."""

from __future__ import annotations

import pytest

from porto_sdk import PortoClient
from porto_sdk.config import PortoConfig, ProviderRuntimeConfig
from porto_sdk.errors import PortoError, PortoErrorCode
from tests.support.bound_provider import bound_provider


def _bound(porto_data_path: str, provider: str):
    client = PortoClient(
        PortoConfig(data=porto_data_path, providers={provider: ProviderRuntimeConfig()})
    )
    return bound_provider(client, provider)


@pytest.mark.offline
def test_absent_envelope_does_not_constrain(porto_data_path) -> None:
    porto = _bound(porto_data_path, "deutschepost").resolve(country_code="DE", weight=20)
    assert porto.product.id == "standardbrief"


@pytest.mark.offline
def test_incompatible_envelope_drops_weight_unique_product(porto_data_path) -> None:
    with pytest.raises(PortoError) as exc:
        _bound(porto_data_path, "deutschepost").resolve(
            country_code="DE", weight=20, envelope_id="C4"
        )
    assert exc.value.code == PortoErrorCode.PORTO_PRODUCT_NOT_FOUND


@pytest.mark.offline
def test_envelope_does_not_select_among_remaining(porto_data_path) -> None:
    with pytest.raises(PortoError) as exc:
        _bound(porto_data_path, "laposte").resolve(country_code="FR", weight=20, envelope_id="DL")
    assert exc.value.code == PortoErrorCode.PORTO_PRODUCT_AMBIGUOUS


@pytest.mark.offline
def test_envelope_unique_after_filter_ukrposhta(porto_data_path) -> None:
    bound = _bound(porto_data_path, "ukrposhta")
    dl = bound.resolve(country_code="UA", weight=20, envelope_id="DL")
    assert dl.product.id == "lyst_standartnyi"
    b4 = bound.resolve(country_code="UA", weight=20, envelope_id="B4")
    assert b4.product.id == "dokument"
