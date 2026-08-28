"""
Internetmarke authentication error classification.

Provider-specific DHL/Portokasse response semantics are interpreted here only.
The mapper emits stable PORTO_* codes plus adapter diagnostics and a nested
provider_error payload for consumers. Generic SDK core must not re-parse
provider body text.

DHL documents that until the Portokasse user approves the business application
(Freigabe under Geschäftsanwendungen), token retrieval returns HTTP 401.
See: https://developer.dhl.com/api-reference/deutsche-post-internetmarke-post-paket-deutschland
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ....errors import PortoErrorCode

_BODY_PREVIEW_LIMIT = 2000
_ERR_CODE_RE = re.compile(r"\bERR_\d+\b", re.IGNORECASE)


class InternetmarkeAuthEndpoint(str, Enum):
    """Which auth hop failed."""

    DHL_APP_TOKEN = "dhl_app_token"
    PORTOKASSE_USER = "portokasse_user"
    COMBINED_USER = "combined_user"


# Adapter diagnostics (not public PORTO_* codes).
DIAG_UNKNOWN_CHANNEL = "unknown_channel"
DIAG_INVALID_APP_CREDENTIALS = "invalid_app_credentials"
DIAG_INVALID_PORTOKASSE_CREDENTIALS = "invalid_portokasse_credentials"
DIAG_PENDING_PORTOKASSE_APPROVAL = "pending_portokasse_approval"
DIAG_UNKNOWN = "unknown"


@dataclass(frozen=True)
class InternetmarkeAuthErrorInfo:
    code: PortoErrorCode
    message: str
    auth_stage: str
    hint: str
    retryable: bool
    diagnostic_reason: str
    provider_error: dict[str, Any]
    user_action: str | None = None
    triggers_portokasse_freigabe_email: bool = False

    def details(self) -> dict[str, Any]:
        """Public details: opaque provider_error only."""
        bag = dict(self.provider_error)
        bag["reason"] = self.diagnostic_reason
        bag["stage"] = self.auth_stage
        if self.hint:
            bag["hint"] = self.hint
        if self.user_action is not None:
            bag["action"] = self.user_action
        if self.triggers_portokasse_freigabe_email:
            bag["triggers_approval_email"] = True
        return {"provider_error": bag}


def _body_lower(response_body: str) -> str:
    return (response_body or "").lower()


def _looks_like_unknown_channel(body_lower: str) -> bool:
    return "unknown channel" in body_lower


def _looks_like_dhl_app_denied(body_lower: str) -> bool:
    return (
        "unauthorized for given resource" in body_lower
        or "invalid client identifier" in body_lower
        or _looks_like_unknown_channel(body_lower)
    )


def _looks_like_portokasse_app_not_approved(body_lower: str) -> bool:
    markers = (
        "geschäftsanwendungen",
        "geschaeftsanwendungen",
        "business application",
        "freigabe",
        "nicht freigegeben",
        "anwendung nicht",
        "applikations-freigabe",
        "not authorized by user",
        "application is not authorized",
        "genericuserauthenticationerror",
    )
    return any(marker in body_lower for marker in markers)


def _looks_like_invalid_portokasse_credentials(body_lower: str) -> bool:
    markers = (
        "invalid password",
        "wrong password",
        "falsches passwort",
        "ungültig",
        "ungueltig",
        "login failed",
        "anmeldung fehlgeschlagen",
    )
    return any(marker in body_lower for marker in markers)


def build_provider_error(
    http_status: int,
    response_body: str,
    *,
    endpoint: InternetmarkeAuthEndpoint,
) -> dict[str, Any]:
    """Structure original provider signal for PortoError.details (opaque to core)."""
    raw = response_body or ""
    preview = raw[:_BODY_PREVIEW_LIMIT]
    provider_code: str | None = None
    provider_title: str | None = None
    provider_detail: str | None = None

    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        data = None

    if isinstance(data, dict):
        title = data.get("title")
        detail = data.get("detail")
        code = data.get("code")
        message = data.get("message") or data.get("description")
        if isinstance(title, str) and title.strip():
            provider_title = title.strip()
        if isinstance(detail, str) and detail.strip():
            provider_detail = detail.strip()
        elif isinstance(message, str) and message.strip():
            provider_detail = message.strip()
        if isinstance(code, str) and code.strip():
            provider_code = code.strip()
        elif provider_title and provider_title.upper().startswith("ERR_"):
            provider_code = provider_title

    if provider_code is None:
        match = _ERR_CODE_RE.search(raw)
        if match:
            provider_code = match.group(0).upper()

    if provider_detail is None and preview and not isinstance(data, dict):
        provider_detail = preview[:500]

    return {
        "http_status": http_status,
        "provider_code": provider_code,
        "provider_title": provider_title,
        "provider_detail": provider_detail,
        "body_preview": preview,
        "endpoint": endpoint.value,
    }


def _dhl_app_denied_hint(*, unknown_channel: bool) -> str:
    if unknown_channel:
        return (
            "DHL rejected this developer-app channel (unknown channel). "
            "Use the DHL Developer Portal app subscribed for "
            "Post & Parcel Germany / Internetmarke — not a stale/Wing-mapped app — "
            "and update PORTO_DEUTSCHEPOST_INTERNETMARKE_DHL_API_KEY / _SECRET."
        )
    return (
        "Confirm DHL Developer Portal API key/secret and API subscription "
        "for Post & Parcel Germany / Internetmarke."
    )


def _info(
    *,
    code: PortoErrorCode,
    message: str,
    auth_stage: str,
    hint: str,
    diagnostic_reason: str,
    provider_error: dict[str, Any],
    user_action: str | None = None,
    triggers_portokasse_freigabe_email: bool = False,
) -> InternetmarkeAuthErrorInfo:
    return InternetmarkeAuthErrorInfo(
        code=code,
        message=message,
        auth_stage=auth_stage,
        hint=hint,
        retryable=False,
        diagnostic_reason=diagnostic_reason,
        provider_error=provider_error,
        user_action=user_action,
        triggers_portokasse_freigabe_email=triggers_portokasse_freigabe_email,
    )


def map_internetmarke_auth_http_error(
    http_status: int,
    response_body: str,
    *,
    endpoint: InternetmarkeAuthEndpoint,
    app_token_obtained: bool = False,
) -> InternetmarkeAuthErrorInfo:
    """Map an Internetmarke auth HTTP failure to a stable PORTO_* error + diagnostics."""
    body_lower = _body_lower(response_body)
    provider_error = build_provider_error(http_status, response_body, endpoint=endpoint)
    unknown_channel = _looks_like_unknown_channel(body_lower)

    if endpoint == InternetmarkeAuthEndpoint.DHL_APP_TOKEN:
        if _looks_like_dhl_app_denied(body_lower):
            diagnostic = DIAG_UNKNOWN_CHANNEL if unknown_channel else DIAG_INVALID_APP_CREDENTIALS
            return _info(
                code=PortoErrorCode.PORTO_AUTH_DENIED,
                message="DHL developer app not authorized for this API",
                auth_stage="dhl_developer_app",
                hint=_dhl_app_denied_hint(unknown_channel=unknown_channel),
                diagnostic_reason=diagnostic,
                provider_error=provider_error,
            )
        if http_status in {401, 403}:
            return _info(
                code=PortoErrorCode.PORTO_AUTH_FAILED,
                message="DHL developer app credentials missing, invalid, or rejected",
                auth_stage="dhl_developer_app",
                hint=_dhl_app_denied_hint(unknown_channel=False),
                diagnostic_reason=DIAG_INVALID_APP_CREDENTIALS,
                provider_error=provider_error,
            )
        return _info(
            code=PortoErrorCode.PORTO_AUTH_FAILED,
            message=f"INTERNETMARKE DHL app auth failed (HTTP {http_status})",
            auth_stage="dhl_developer_app",
            hint="Inspect provider_error in error details.",
            diagnostic_reason=DIAG_INVALID_APP_CREDENTIALS,
            provider_error=provider_error,
        )

    if endpoint in {
        InternetmarkeAuthEndpoint.PORTOKASSE_USER,
        InternetmarkeAuthEndpoint.COMBINED_USER,
    }:
        if _looks_like_dhl_app_denied(body_lower) and endpoint == (
            InternetmarkeAuthEndpoint.COMBINED_USER
        ):
            diagnostic = DIAG_UNKNOWN_CHANNEL if unknown_channel else DIAG_INVALID_APP_CREDENTIALS
            return _info(
                code=PortoErrorCode.PORTO_AUTH_DENIED,
                message="DHL developer app not authorized for this API",
                auth_stage="dhl_developer_app",
                hint=_dhl_app_denied_hint(unknown_channel=unknown_channel),
                diagnostic_reason=diagnostic,
                provider_error=provider_error,
            )

        if (
            http_status in {401, 403}
            or _looks_like_portokasse_app_not_approved(body_lower)
            or (
                http_status == 401
                and endpoint == InternetmarkeAuthEndpoint.PORTOKASSE_USER
                and app_token_obtained
            )
        ):
            if _looks_like_invalid_portokasse_credentials(body_lower):
                return _info(
                    code=PortoErrorCode.PORTO_AUTH_FAILED,
                    message="Portokasse username or password rejected",
                    auth_stage="portokasse_credentials",
                    hint="Verify Portokasse username and password in configuration.",
                    diagnostic_reason=DIAG_INVALID_PORTOKASSE_CREDENTIALS,
                    provider_error=provider_error,
                )
            return _info(
                code=PortoErrorCode.PORTO_LINKAGE_PENDING,
                message="Portokasse user has not approved this business application",
                auth_stage="portokasse_linkage",
                hint=(
                    "Per DHL documentation, missing Freigabe returns HTTP 401 on token retrieval. "
                    "Deutsche Post emails the Portokasse user with a Freigabe request. "
                    "Approve under Portokasse → Meine Daten → Geschäftsanwendungen, then retry."
                ),
                diagnostic_reason=DIAG_PENDING_PORTOKASSE_APPROVAL,
                provider_error=provider_error,
                user_action="portokasse_geschaeftsanwendungen_freigabe",
                triggers_portokasse_freigabe_email=True,
            )

        if http_status == 401:
            return _info(
                code=PortoErrorCode.PORTO_AUTH_FAILED,
                message="INTERNETMARKE authentication failed (HTTP 401)",
                auth_stage="portokasse_credentials",
                hint=(
                    "Verify Portokasse credentials or approve the app under Geschäftsanwendungen."
                ),
                diagnostic_reason=DIAG_INVALID_PORTOKASSE_CREDENTIALS,
                provider_error=provider_error,
            )

        return _info(
            code=PortoErrorCode.PORTO_AUTH_FAILED,
            message=f"INTERNETMARKE authentication failed (HTTP {http_status})",
            auth_stage="unknown",
            hint="Inspect provider_error in error details.",
            diagnostic_reason=DIAG_UNKNOWN,
            provider_error=provider_error,
        )

    return _info(
        code=PortoErrorCode.PORTO_AUTH_FAILED,
        message=f"INTERNETMARKE authentication failed (HTTP {http_status})",
        auth_stage="unknown",
        hint="Inspect provider_error in error details.",
        diagnostic_reason=DIAG_UNKNOWN,
        provider_error=provider_error,
    )
