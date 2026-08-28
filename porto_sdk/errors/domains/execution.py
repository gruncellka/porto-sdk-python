"""Wallet / mark-execution error factories."""

from __future__ import annotations

from typing import Any

from porto_sdk.errors import ProviderError
from porto_sdk.errors.codes import PortoErrorCode


def raise_wallet_insufficient(
    message: str,
    *,
    required_cents: int,
    wallet_account_id: str | None = None,
    provider: str | None = None,
    wire: str | None = None,
    upstream_code: str | None = None,
    status_code: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    payload = dict(details or {})
    payload["required_cents"] = required_cents
    if wallet_account_id:
        payload["wallet_account_id"] = wallet_account_id
    raise ProviderError(
        message,
        PortoErrorCode.PORTO_WALLET_INSUFFICIENT,
        status_code=status_code,
        details=payload,
        provider=provider,
        wire=wire,
        upstream_code=upstream_code,
    )
