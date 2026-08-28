"""Adapter tests: Internetmarke auth responses map to canonical PORTO_* + opaque provider_error."""

from porto_sdk.adapters.deutschepost.internetmarke.auth_errors import (
    DIAG_INVALID_PORTOKASSE_CREDENTIALS,
    DIAG_PENDING_PORTOKASSE_APPROVAL,
    DIAG_UNKNOWN_CHANNEL,
    InternetmarkeAuthEndpoint,
    map_internetmarke_auth_http_error,
)
from porto_sdk.errors import PortoErrorCode


def _reason(info) -> str:
    return info.details()["provider_error"]["reason"]


def test_dhl_app_token_unauthorized_resource_maps_to_auth_denied() -> None:
    info = map_internetmarke_auth_http_error(
        401,
        '{"status":401,"detail":"Unauthorized for given resource."}',
        endpoint=InternetmarkeAuthEndpoint.DHL_APP_TOKEN,
    )
    assert info.code == PortoErrorCode.PORTO_AUTH_DENIED
    assert _reason(info) != DIAG_UNKNOWN_CHANNEL
    assert info.details() == {"provider_error": info.details()["provider_error"]}
    assert info.details()["provider_error"]["http_status"] == 401


def test_unknown_channel_maps_to_auth_denied_with_provider_payload() -> None:
    body = (
        '{"status":400,"title":"ERR_1000",'
        '"detail":"Invalid request. Unknown channel: nzlnllk-0001 !"}'
    )
    info = map_internetmarke_auth_http_error(
        400,
        body,
        endpoint=InternetmarkeAuthEndpoint.COMBINED_USER,
    )
    assert info.code == PortoErrorCode.PORTO_AUTH_DENIED
    details = info.details()
    assert set(details) == {"provider_error"}
    bag = details["provider_error"]
    assert bag["reason"] == DIAG_UNKNOWN_CHANNEL
    assert bag["provider_code"] == "ERR_1000"
    assert "Unknown channel" in (bag["provider_detail"] or "")


def test_portokasse_user_401_after_app_token_maps_to_linkage_pending() -> None:
    info = map_internetmarke_auth_http_error(
        401,
        '{"status":401,"title":"Unauthorized","detail":"Unauthorized"}',
        endpoint=InternetmarkeAuthEndpoint.PORTOKASSE_USER,
        app_token_obtained=True,
    )
    assert info.code == PortoErrorCode.PORTO_LINKAGE_PENDING
    assert _reason(info) == DIAG_PENDING_PORTOKASSE_APPROVAL


def test_portokasse_user_403_maps_to_linkage_pending() -> None:
    info = map_internetmarke_auth_http_error(
        403,
        '{"detail":"Geschäftsanwendungen Freigabe fehlt"}',
        endpoint=InternetmarkeAuthEndpoint.PORTOKASSE_USER,
        app_token_obtained=True,
    )
    assert info.code == PortoErrorCode.PORTO_LINKAGE_PENDING


def test_combined_user_401_with_freigabe_hint() -> None:
    info = map_internetmarke_auth_http_error(
        401,
        "Applikations-Freigabe in Portokasse erforderlich",
        endpoint=InternetmarkeAuthEndpoint.COMBINED_USER,
    )
    assert info.code == PortoErrorCode.PORTO_LINKAGE_PENDING
    assert _reason(info) == DIAG_PENDING_PORTOKASSE_APPROVAL


def test_combined_user_401_invalid_password_maps_to_auth_failed() -> None:
    info = map_internetmarke_auth_http_error(
        401,
        "Invalid password for Portokasse user",
        endpoint=InternetmarkeAuthEndpoint.COMBINED_USER,
    )
    assert info.code == PortoErrorCode.PORTO_AUTH_FAILED
    assert _reason(info) == DIAG_INVALID_PORTOKASSE_CREDENTIALS
