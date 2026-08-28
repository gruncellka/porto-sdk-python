"""porto-data error factories."""

from __future__ import annotations

from typing import Any, NoReturn

from porto_sdk.errors import DataError
from porto_sdk.errors.codes import PortoErrorCode


def raise_data_not_found(
    message: str,
    *,
    path: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> NoReturn:
    payload = dict(details or {})
    if path:
        payload["path"] = path
    if entity_id:
        payload["entity_id"] = entity_id
    raise DataError(message, PortoErrorCode.PORTO_DATA_NOT_FOUND, details=payload)


def raise_data_invalid(
    message: str,
    *,
    path: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> NoReturn:
    payload = dict(details or {})
    if path:
        payload["path"] = path
    if entity_id:
        payload["entity_id"] = entity_id
    raise DataError(message, PortoErrorCode.PORTO_DATA_INVALID, details=payload)


def raise_data_corrupted(
    message: str,
    *,
    path: str | None = None,
    expected: str | None = None,
    actual: str | None = None,
    details: dict[str, Any] | None = None,
) -> NoReturn:
    payload = dict(details or {})
    if path:
        payload["path"] = path
    if expected:
        payload["expected"] = expected
    if actual:
        payload["actual"] = actual
    raise DataError(message, PortoErrorCode.PORTO_DATA_CORRUPTED, details=payload)
