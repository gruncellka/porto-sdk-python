"""Step definitions for Internetmarke adapter error features."""

from __future__ import annotations

import os
from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from porto_sdk import PortoClient, PortoConfig
from porto_sdk.adapters.deutschepost.internetmarke.auth import InternetmarkeAuth
from porto_sdk.adapters.deutschepost.internetmarke.auth_errors import (
    InternetmarkeAuthEndpoint,
    map_internetmarke_auth_http_error,
)
from porto_sdk.adapters.deutschepost.internetmarke.bootstrap import (
    get_internetmarke_base_url,
    load_internetmarke_config,
)
from porto_sdk.adapters.deutschepost.internetmarke.utils import (
    extract_internetmarke_vendor_error_code,
    map_internetmarke_error_code,
)
from porto_sdk.config import ProviderRuntimeConfig, WireConfig
from porto_sdk.errors import PortoError, PortoErrorCode, map_provider_error
from porto_sdk.execution import PortoMarkRequest
from porto_sdk.requires import RECIPIENT as REQUIRE_RECIPIENT
from porto_sdk.requires import SENDER as REQUIRE_SENDER
from porto_sdk.types import Address
from tests.bdd.steps.async_util import run_async
from tests.support.addresses import licko_sender
from tests.support.bound_provider import bound_provider
from tests.support.porto_features_path import get_porto_data_path

MARK_EXECUTION_TRIGGERS: dict[str, dict[str, Any]] = {
    "wallet_balance_not_enough": {
        "status": 400,
        "body": {
            "statusCode": "400",
            "title": "walletBalanceNotEnough",
            "description": "TEST-WALLET-ID",
            "instance": "PCF-A1032",
        },
    },
}

SENDER = licko_sender()

AUTH_TRIGGERS: dict[str, dict[str, Any]] = {
    "unauthorized_prose": {
        "status": 401,
        "body": "Unauthorized",
        "endpoint": InternetmarkeAuthEndpoint.COMBINED_USER,
        "app_token_obtained": False,
    },
    "dhl_app_token_denied": {
        "status": 401,
        "body": '{"status":401,"detail":"Unauthorized for given resource."}',
        "endpoint": InternetmarkeAuthEndpoint.DHL_APP_TOKEN,
        "app_token_obtained": False,
    },
    "invalid_portokasse_password": {
        "status": 401,
        "body": "Invalid password for Portokasse user",
        "endpoint": InternetmarkeAuthEndpoint.COMBINED_USER,
        "app_token_obtained": False,
    },
    "portokasse_linkage_pending": {
        "status": 401,
        "body": '{"status":401,"title":"Unauthorized","detail":"Unauthorized"}',
        "endpoint": InternetmarkeAuthEndpoint.PORTOKASSE_USER,
        "app_token_obtained": True,
    },
}


def _capture_error(error: object) -> dict[str, str]:
    code = getattr(error, "code", None)
    if hasattr(code, "value"):
        code = code.value
    return {
        "code": str(code or PortoErrorCode.PORTO_MARK_FAILED.value),
        "message": error.message if isinstance(error, Exception) else str(error),
    }


def _client_with_wires(
    *,
    dhl_api_key: str | None = None,
    password: str | None = None,
) -> PortoClient | None:
    im = load_internetmarke_config("deutschepost", dict(os.environ))
    if im is None:
        return None
    creds = dict(im.credentials or {})
    if not (
        creds.get("username")
        and creds.get("password")
        and creds.get("dhl_api_key")
        and creds.get("dhl_api_secret")
    ):
        return None
    if dhl_api_key is not None:
        creds["dhl_api_key"] = dhl_api_key
    if password is not None:
        creds["password"] = password
    return PortoClient(
        PortoConfig(
            data=get_porto_data_path(),
            providers={
                "deutschepost": ProviderRuntimeConfig(
                    wires={"internetmarke": WireConfig(base_url=im.base_url, credentials=creds)},
                )
            },
        )
    )


def _resolve_porto(client, *, weight: int = 20):
    return bound_provider(client).resolve(
        country_code="DE",
        weight=weight,
    )


@when("I attempt to create a mark")
def when_attempt_create_mark(context):
    client = context["client"]

    async def _run() -> None:
        invalid = context.get("invalid_mark_destination")
        porto = context.get("resolved_porto")
        if porto is None:
            porto = _resolve_porto(
                client,
                weight=context.get("weight", 20),
            )
            if invalid:
                porto = porto.model_copy(
                    update={"requires": frozenset({REQUIRE_SENDER, REQUIRE_RECIPIENT})}
                )
        if "sender" in context or "recipient" in context:
            sender = context.get("sender")
            recipient = context.get("recipient")
        elif invalid:
            sender = SENDER
            recipient = Address(
                name="x",
                street="x",
                house_number="1",
                postal_code="1",
                locality="x",
                country_code="DE",
            )
        else:
            sender = None
            recipient = None
        try:
            await bound_provider(client).mark(
                PortoMarkRequest(
                    porto=porto,
                    sender=sender,
                    recipient=recipient,
                )
            )
            context["mark_error"] = None
        except Exception as exc:  # noqa: BLE001 — BDD capture
            context["mark_error"] = _capture_error(exc)

    run_async(_run())


@given("Internetmarke credentials are not configured")
def given_im_credentials_absent():
    """Keep the default test client (no live Internetmarke wires)."""


@given("Internetmarke credentials are configured")
def given_im_credentials_configured(context):
    configured = _client_with_wires()
    if configured is None:
        pytest.skip("Internetmarke credentials not available")
    context["client"] = configured


@given("Internetmarke DHL app credentials are invalid for testing")
def given_im_dhl_invalid(context):
    configured = _client_with_wires(dhl_api_key="invalid-dhl-app-key-for-bdd")
    if configured is None:
        pytest.skip("Internetmarke credentials not available")
    context["client"] = configured


@given("Internetmarke Portokasse password is invalid for testing")
def given_im_portokasse_invalid(context):
    configured = _client_with_wires(password="definitely-wrong-password-for-bdd")
    if configured is None:
        pytest.skip("Internetmarke credentials not available")
    context["client"] = configured


@given(parsers.parse('Internetmarke auth test trigger is "{trigger}"'))
def given_im_auth_trigger(trigger: str, context):
    context["auth_trigger_detail"] = trigger.strip()


@given(parsers.parse('Internetmarke mark-execution test trigger is "{trigger}"'))
def given_im_mark_execution_trigger(trigger: str, context):
    context["mark_execution_trigger_detail"] = trigger.strip()


@given("the mark destination address is invalid for testing")
def given_invalid_mark_destination(context):
    context["invalid_mark_destination"] = True


@when("I map the Internetmarke auth HTTP error for testing")
def when_map_im_auth_http_error(context):
    trigger = context.get("auth_trigger_detail") or "unauthorized_prose"
    if trigger == "unauthorized_prose":
        mapped = map_provider_error("deutschepost", "internetmarke", "Unauthorized", 401)
        context["mark_error"] = {"code": mapped.code.value, "message": mapped.message}
        return
    spec = AUTH_TRIGGERS.get(trigger)
    if spec is None:
        raise RuntimeError(f"unknown Internetmarke auth test trigger: {trigger}")
    info = map_internetmarke_auth_http_error(
        spec["status"],
        spec["body"],
        endpoint=spec["endpoint"],
        app_token_obtained=spec["app_token_obtained"],
    )
    mapped = PortoError(
        info.message,
        info.code,
        status_code=spec["status"],
        details=info.details(),
        retryable=info.retryable,
        provider="deutschepost",
        wire="internetmarke",
    )
    context["mark_error"] = {"code": mapped.code.value, "message": mapped.message}


@when("I map the Internetmarke mark-execution HTTP error for testing")
def when_map_im_mark_execution_http_error(context):
    trigger = context.get("mark_execution_trigger_detail") or "wallet_balance_not_enough"
    spec = MARK_EXECUTION_TRIGGERS.get(trigger)
    if spec is None:
        raise RuntimeError(f"unknown Internetmarke mark-execution test trigger: {trigger}")
    body = spec["body"]
    vendor = extract_internetmarke_vendor_error_code(body)
    code = map_internetmarke_error_code(vendor, int(spec["status"]))
    context["mark_error"] = {
        "code": code.value,
        "message": f"mark execution mapped: {vendor}",
    }


@when("I probe Internetmarke authentication")
def when_probe_im_auth(context):
    client = context["client"]
    im = client.config.wires_for("deutschepost") or {}
    wire = im.get("internetmarke") if isinstance(im, dict) else None
    if wire is None:
        wire = load_internetmarke_config("deutschepost", dict(os.environ))
    if wire is None:
        pytest.skip("Internetmarke credentials not available")
    wired = wire.credentials or {}
    auth = InternetmarkeAuth(
        wired.get("username") or "",
        wired.get("password") or "",
        api_key=wired.get("dhl_api_key"),
        api_secret=wired.get("dhl_api_secret"),
        base_url=get_internetmarke_base_url(wire),
        partner_id=wired.get("partner_id"),
    )

    async def _run() -> None:
        try:
            await auth.authenticate()
            context["mark_error"] = None
        except Exception as exc:  # noqa: BLE001 — BDD capture
            context["mark_error"] = _capture_error(exc)

    run_async(_run())


@then("mark creation should fail")
def then_mark_creation_fails(context):
    assert context.get("mark_error") is not None
