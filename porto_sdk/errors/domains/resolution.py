"""Resolution pipeline error factories."""

from __future__ import annotations

from typing import Any, NoReturn

from porto_sdk.errors import PortoError
from porto_sdk.errors.codes import PortoErrorCode


def raise_destination_invalid(
    message: str,
    *,
    country_code: str,
    reason: str | None = None,
    status_code: int | None = None,
    details: dict[str, Any] | None = None,
) -> NoReturn:
    payload = dict(details or {})
    payload["country_code"] = country_code
    if reason:
        payload["reason"] = reason
    raise PortoError(
        message,
        PortoErrorCode.PORTO_DESTINATION_INVALID,
        status_code=status_code,
        details=payload,
    )


def raise_product_not_found(
    message: str,
    *,
    zone_id: str,
    weight_tier_id: str,
    product_id: str | None = None,
    candidates: list[str] | None = None,
    status_code: int | None = None,
    details: dict[str, Any] | None = None,
) -> NoReturn:
    payload = dict(details or {})
    payload.update(
        {
            "zone_id": zone_id,
            "weight_tier_id": weight_tier_id,
        }
    )
    if product_id:
        payload["product_id"] = product_id
    if candidates is not None:
        payload["candidates"] = candidates
    raise PortoError(
        message,
        PortoErrorCode.PORTO_PRODUCT_NOT_FOUND,
        status_code=status_code,
        details=payload,
    )


def raise_product_ambiguous(
    message: str,
    *,
    zone_id: str,
    weight_tier_id: str,
    candidates: list[str],
    status_code: int | None = None,
    details: dict[str, Any] | None = None,
) -> NoReturn:
    payload = dict(details or {})
    payload.update(
        {
            "zone_id": zone_id,
            "weight_tier_id": weight_tier_id,
            "candidates": candidates,
        }
    )
    raise PortoError(
        message,
        PortoErrorCode.PORTO_PRODUCT_AMBIGUOUS,
        status_code=status_code,
        details=payload,
    )


def raise_price_not_found(
    message: str,
    *,
    product_id: str,
    zone_id: str,
    weight_tier_id: str,
    status_code: int | None = None,
    details: dict[str, Any] | None = None,
) -> NoReturn:
    payload = dict(details or {})
    payload.update(
        {
            "product_id": product_id,
            "zone_id": zone_id,
            "weight_tier_id": weight_tier_id,
        }
    )
    raise PortoError(
        message,
        PortoErrorCode.PORTO_PRICE_NOT_FOUND,
        status_code=status_code,
        details=payload,
    )


def raise_too_heavy(
    message: str,
    *,
    weight: int,
    max_weight: int | None = None,
    status_code: int | None = None,
    details: dict[str, Any] | None = None,
) -> NoReturn:
    payload = dict(details or {})
    payload["weight"] = weight
    if max_weight is not None:
        payload["max_weight"] = max_weight
    raise PortoError(
        message,
        PortoErrorCode.PORTO_TOO_HEAVY,
        status_code=status_code,
        details=payload,
    )
