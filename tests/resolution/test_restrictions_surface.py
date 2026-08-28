"""Public restrictions surface + resolve attachment."""

from __future__ import annotations

from porto_sdk import PortoClient
from porto_sdk.config import PortoConfig, ProviderRuntimeConfig
from tests.support.bound_provider import bound_provider


def _client(porto_data_path: str, provider: str = "deutschepost") -> PortoClient:
    return PortoClient(
        PortoConfig(data=porto_data_path, providers={provider: ProviderRuntimeConfig()})
    )


def test_unrestricted_country_has_empty_restriction_result(porto_data_path) -> None:
    client = _client(porto_data_path)
    found = client.provider("deutschepost").restrictions.check("DE")
    assert found.impact is None
    assert found.legal == ()
    assert found.routing == ()

    porto = bound_provider(client).resolve(country_code="DE", weight=20, envelope_id="DL")
    assert porto.restrictions == found
    assert porto.warnings == []


def test_country_resolve_returns_ua_legal_items_with_warn_aggregate(porto_data_path) -> None:
    client = _client(porto_data_path)
    found = client.provider("deutschepost").restrictions.check("UA")
    assert found.impact == "warn"
    assert {item.region_code for item in found.legal} == {
        "UA-09",
        "UA-14",
        "UA-23",
        "UA-40",
        "UA-43",
        "UA-65",
    }
    assert found.routing == ()

    porto = bound_provider(client).resolve(country_code="UA", weight=20, envelope_id="DL")
    assert porto.restrictions == found
    # Country resolve never promotes a child regional block.
    assert porto.restrictions.impact == "warn"


def test_kherson_partial_region_warns_via_check(porto_data_path) -> None:
    found = _client(porto_data_path).provider("deutschepost").restrictions.check("UA", "UA-65")
    assert found.impact == "warn"
    assert len(found.legal) == 1
    item = found.legal[0]
    assert item.region_code == "UA-65"
    assert item.partial is True
    assert item.jurisdictions[0].jurisdiction == "EU"
    assert item.jurisdictions[0].reference.startswith("https://eur-lex.europa.eu")
    assert found.routing == ()


def test_fully_matched_legal_territory_blocks_via_check(porto_data_path) -> None:
    found = _client(porto_data_path).provider("deutschepost").restrictions.check("UA", "UA-43")
    assert found.impact == "block"
    assert len(found.legal) == 1
    assert found.legal[0].region_code == "UA-43"
    assert found.legal[0].partial is False


def test_unaffected_ua_region_has_no_restriction_via_check(porto_data_path) -> None:
    found = _client(porto_data_path).provider("deutschepost").restrictions.check("UA", "UA-32")
    assert found.impact is None
    assert found.legal == ()
    assert found.routing == ()


def test_cyprus_routing_warns_via_check(porto_data_path) -> None:
    found = _client(porto_data_path).provider("deutschepost").restrictions.check("CY", "CY-01")
    assert found.impact == "warn"
    assert found.legal == ()
    assert len(found.routing) == 1
    item = found.routing[0]
    assert item.authority == "CY"
    assert item.region_code == "CY-01"
    assert item.partial is True


def test_laposte_matches_deutschepost_on_eu_jurisdiction(porto_data_path) -> None:
    dp = (
        _client(porto_data_path, "deutschepost")
        .provider("deutschepost")
        .restrictions.check("UA", "UA-65")
    )
    lp = _client(porto_data_path, "laposte").provider("laposte").restrictions.check("UA", "UA-65")
    assert dp.legal[0].jurisdictions[0].reference == lp.legal[0].jurisdictions[0].reference


def test_swisspost_uses_ch_jurisdiction(porto_data_path) -> None:
    found = (
        _client(porto_data_path, "swisspost")
        .provider("swisspost")
        .restrictions.check("UA", "UA-65")
    )
    assert found.legal[0].jurisdictions[0].jurisdiction == "CH"
    assert "seco.admin.ch" in (found.legal[0].jurisdictions[0].reference or "")


def test_ukrposhta_uses_ua_jurisdiction(porto_data_path) -> None:
    found = (
        _client(porto_data_path, "ukrposhta")
        .provider("ukrposhta")
        .restrictions.check("UA", "UA-65")
    )
    assert found.legal[0].jurisdictions[0].jurisdiction == "UA"
    assert found.legal[0].jurisdictions[0].reference == (
        "https://zakon.rada.gov.ua/laws/show/1207-18"
    )


def test_routing_same_across_providers(porto_data_path) -> None:
    dp = (
        _client(porto_data_path, "deutschepost")
        .provider("deutschepost")
        .restrictions.check("CY", "CY-06")
    )
    ch = (
        _client(porto_data_path, "swisspost").provider("swisspost").restrictions.check("CY", "CY-06")
    )
    assert dp == ch
