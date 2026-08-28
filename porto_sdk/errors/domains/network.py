"""Network / transport error factories."""

from __future__ import annotations

from typing import Any

from porto_sdk.errors import PortoError, TransportError
from porto_sdk.errors.codes import PortoErrorCode


def map_http_status_to_network_code(status_code: int | None) -> PortoErrorCode:
    if status_code == 429:
        return PortoErrorCode.PORTO_NETWORK_RATE_LIMITED
    if status_code == 408:
        return PortoErrorCode.PORTO_NETWORK_TIMEOUT
    if status_code and status_code >= 500:
        return PortoErrorCode.PORTO_NETWORK_UNAVAILABLE
    return PortoErrorCode.PORTO_NETWORK_UNAVAILABLE


def raise_network_timeout(
    message: str,
    *,
    http_status: int | None = None,
    retryable: bool = True,
    provider: str | None = None,
    wire: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    payload = dict(details or {})
    if http_status is not None:
        payload["http_status"] = http_status
    payload["retryable"] = retryable
    raise TransportError(
        message,
        PortoErrorCode.PORTO_NETWORK_TIMEOUT,
        status_code=http_status,
        details=payload,
        retryable=retryable,
        provider=provider,
        wire=wire,
    )


def raise_network_unavailable(
    message: str,
    *,
    http_status: int | None = None,
    retryable: bool = True,
    provider: str | None = None,
    wire: str | None = None,
    upstream_code: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    payload = dict(details or {})
    if http_status is not None:
        payload["http_status"] = http_status
    payload["retryable"] = retryable
    raise TransportError(
        message,
        PortoErrorCode.PORTO_NETWORK_UNAVAILABLE,
        status_code=http_status,
        details=payload,
        retryable=retryable,
        provider=provider,
        wire=wire,
        upstream_code=upstream_code,
    )


def map_transport_error(
    provider: str,
    wire: str,
    raw_error: Any,
    status_code: int | None = None,
) -> PortoError:
    """Single entrypoint for adapter HTTP/transport failures."""
    msg = str(raw_error) if isinstance(raw_error, Exception) else str(raw_error)
    upper = msg.upper()
    if status_code == 429 or "RATE" in upper:
        code = PortoErrorCode.PORTO_NETWORK_RATE_LIMITED
    elif status_code == 408 or "TIMEOUT" in upper or "ETIMEDOUT" in upper:
        code = PortoErrorCode.PORTO_NETWORK_TIMEOUT
    elif (
        status_code
        and status_code >= 500
        or "ECONNREFUSED" in upper
        or "DNS" in upper
        or "NETWORK" in upper
    ):
        code = PortoErrorCode.PORTO_NETWORK_UNAVAILABLE
    else:
        code = map_http_status_to_network_code(status_code)
    if code == PortoErrorCode.PORTO_NETWORK_RATE_LIMITED:
        retryable = True
    elif code == PortoErrorCode.PORTO_NETWORK_TIMEOUT:
        retryable = status_code in {408, 429} or (status_code is not None and status_code >= 500)
    elif code == PortoErrorCode.PORTO_NETWORK_UNAVAILABLE:
        retryable = status_code is not None and status_code >= 500
    else:
        retryable = False
    upstream_code: str | None = None
    if hasattr(raw_error, "code") and isinstance(raw_error.code, str):
        upstream_code = raw_error.code
    return TransportError(
        msg or "Provider request failed",
        code,
        status_code=status_code,
        details={"name": type(raw_error).__name__} if isinstance(raw_error, Exception) else None,
        retryable=retryable,
        provider=provider,
        wire=wire,
        upstream_code=upstream_code,
    )
