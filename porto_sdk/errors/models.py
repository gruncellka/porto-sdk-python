"""Shared error helpers and mapping utilities."""

from __future__ import annotations

from typing import Any

from porto_sdk.errors.codes import PortoErrorCode
from porto_sdk.errors.exceptions import (
    AuthenticationError,
    PortoError,
    ProviderError,
)


def map_provider_error(
    provider: str,
    wire: str,
    raw_error: Any,
    status_code: int | None = None,
) -> PortoError:
    """Map raw adapter/provider errors to PortoError for public consumers."""
    if isinstance(raw_error, PortoError):
        return raw_error

    from porto_sdk.errors.domains.network import map_transport_error

    msg = str(raw_error) if isinstance(raw_error, Exception) else str(raw_error)
    upper = msg.upper()

    if status_code == 401 or "UNAUTHORIZED" in upper:
        upstream_code = getattr(raw_error, "code", None) if hasattr(raw_error, "code") else None
        return AuthenticationError(
            msg or "Authentication failed",
            PortoErrorCode.PORTO_AUTH_FAILED,
            status_code=status_code,
            provider=provider,
            wire=wire,
            upstream_code=upstream_code if isinstance(upstream_code, str) else None,
        )
    if status_code == 403:
        return AuthenticationError(
            msg or "Authentication denied",
            PortoErrorCode.PORTO_AUTH_DENIED,
            status_code=status_code,
            provider=provider,
            wire=wire,
        )
    if "INSUFFICIENT" in upper or "FUNDS" in upper:
        from porto_sdk.errors.domains.execution import raise_wallet_insufficient

        try:
            raise_wallet_insufficient(
                msg or "Insufficient wallet balance",
                required_cents=0,
                provider=provider,
                wire=wire,
                upstream_code=upper if isinstance(getattr(raw_error, "code", None), str) else None,
                status_code=status_code,
            )
        except ProviderError as exc:
            return exc
    if status_code in {408, 429, 500, 502, 503, 504} or any(
        token in upper for token in ("TIMEOUT", "NETWORK", "ECONNREFUSED", "DNS")
    ):
        return map_transport_error(provider, wire, raw_error, status_code)
    if status_code == 501:
        return ProviderError(
            msg or "Capability not supported",
            PortoErrorCode.PORTO_CAPABILITY_UNSUPPORTED,
            status_code=status_code,
            details={"capability": "unknown", "provider_id": provider, "wire": wire},
            provider=provider,
            wire=wire,
            retryable=False,
        )

    return ProviderError(
        msg or "Provider request failed",
        PortoErrorCode.PORTO_MARK_FAILED,
        status_code=status_code,
        details={"name": type(raw_error).__name__} if isinstance(raw_error, Exception) else None,
        provider=provider,
        wire=wire,
        provider_error=raw_error,
    )


def redact_sensitive_fields(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return shallow-redacted copy for safe diagnostic logging."""
    if payload is None:
        return None
    redacted: dict[str, Any] = {}
    sensitive_keys = {
        "password",
        "token",
        "authorization",
        "api_key",
        "api_secret",
        "client_secret",
    }
    for key, value in payload.items():
        if key.lower() in sensitive_keys:
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = value
    return redacted
