"""
Fetch mark document bytes from PortoMark.content.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

import httpx

from .errors import PortoErrorCode, TransportError, ValidationError
from .execution import PortoMark, mark_wire
from .time import as_seconds, parse_duration
from .transport.http_client import DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT, HttpClient, Transport

DEFAULT_MARK_FETCH_RETRIES = DEFAULT_MAX_RETRIES
DEFAULT_MARK_FETCH_TIMEOUT = DEFAULT_TIMEOUT
DEFAULT_MARK_FETCH_BACKOFF = timedelta(milliseconds=500)


@dataclass(frozen=True)
class FetchMarkBytesOptions:
    retries: int = DEFAULT_MARK_FETCH_RETRIES
    timeout: timedelta = DEFAULT_MARK_FETCH_TIMEOUT
    backoff: timedelta = DEFAULT_MARK_FETCH_BACKOFF


def _is_remote_content(content: str) -> bool:
    lowered = content.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def normalize_mark_document(
    mark: PortoMark,
    payload: bytes,
    *,
    normalize: Callable[[bytes], bytes] | None = None,
) -> bytes:
    """Canonical document normalization after HTTP download (PDF / PNG, optional adapter)."""
    content_type = (mark.content_type or "").lower()
    if content_type == "application/pdf" or payload.startswith(b"%PDF"):
        return payload
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return payload
    if normalize is not None:
        try:
            return normalize(payload)
        except Exception as exc:
            raise ValidationError(
                "Unsupported mark document payload",
                PortoErrorCode.PORTO_MARK_FAILED,
                status_code=422,
                details={"mark_id": mark.id},
                retryable=False,
                provider=mark.provider,
            ) from exc
    raise ValidationError(
        "Unsupported mark document payload",
        PortoErrorCode.PORTO_MARK_FAILED,
        status_code=422,
        details={"mark_id": mark.id},
        retryable=False,
        provider=mark.provider,
    )


async def _download_mark_payload(
    mark: PortoMark,
    *,
    http_client: Transport | None,
    options: FetchMarkBytesOptions,
) -> bytes:
    if not mark.content:
        raise ValidationError(
            "PortoMark.content is empty",
            PortoErrorCode.PORTO_MARK_FAILED,
            status_code=422,
            details={"mark_id": mark.id},
            retryable=False,
            provider=mark.provider,
            wire=mark_wire(mark) or None,
        )
    if not _is_remote_content(mark.content):
        raise ValidationError(
            "PortoMark.content is not a downloadable URL",
            PortoErrorCode.PORTO_MARK_FAILED,
            status_code=422,
            details={"mark_id": mark.id, "content_prefix": mark.content[:32]},
            retryable=False,
            provider=mark.provider,
            wire=mark_wire(mark) or None,
        )

    owns_client = http_client is None
    client = http_client or HttpClient(
        timeout=options.timeout,
        retries=options.retries,
    )
    try:
        response = await client.request(
            method="GET",
            url=mark.content,
            idempotent=True,
        )
        if response.status_code >= 400:
            retryable = response.status_code >= 500 or response.status_code == 429
            raise TransportError(
                f"Mark document download failed with HTTP {response.status_code}",
                PortoErrorCode.PORTO_MARK_FAILED
                if response.status_code < 500
                else PortoErrorCode.PORTO_NETWORK_UNAVAILABLE,
                status_code=response.status_code,
                details={"mark_id": mark.id, "url": mark.content},
                retryable=retryable,
                provider=mark.provider,
                wire=mark_wire(mark) or None,
            )
        return bytes(response.content)
    finally:
        if owns_client:
            await client.close()


def _download_mark_payload_sync(
    mark: PortoMark,
    *,
    options: FetchMarkBytesOptions,
) -> bytes:
    if not mark.content:
        raise ValidationError(
            "PortoMark.content is empty",
            PortoErrorCode.PORTO_MARK_FAILED,
            status_code=422,
            details={"mark_id": mark.id},
            retryable=False,
            provider=mark.provider,
            wire=mark_wire(mark) or None,
        )
    if not _is_remote_content(mark.content):
        raise ValidationError(
            "PortoMark.content is not a downloadable URL",
            PortoErrorCode.PORTO_MARK_FAILED,
            status_code=422,
            details={"mark_id": mark.id, "content_prefix": mark.content[:32]},
            retryable=False,
            provider=mark.provider,
            wire=mark_wire(mark) or None,
        )

    last_error: Exception | None = None
    for attempt in range(1, options.retries + 1):
        try:
            with httpx.Client(timeout=as_seconds(options.timeout)) as client:
                response = client.get(mark.content)
            if response.status_code >= 400:
                retryable = response.status_code >= 500 or response.status_code == 429
                if retryable and attempt < options.retries:
                    time.sleep(as_seconds(options.backoff) * (2 ** (attempt - 1)))
                    continue
                raise TransportError(
                    f"Mark document download failed with HTTP {response.status_code}",
                    PortoErrorCode.PORTO_MARK_FAILED
                    if response.status_code < 500
                    else PortoErrorCode.PORTO_NETWORK_UNAVAILABLE,
                    status_code=response.status_code,
                    details={"mark_id": mark.id, "url": mark.content},
                    retryable=retryable,
                    provider=mark.provider,
                    wire=mark_wire(mark) or None,
                )
            return bytes(response.content)
        except httpx.TimeoutException as exc:
            last_error = TransportError(
                "Mark document download timed out",
                PortoErrorCode.PORTO_NETWORK_TIMEOUT,
                status_code=408,
                details={"mark_id": mark.id, "url": mark.content},
                retryable=attempt < options.retries,
                provider=mark.provider,
                wire=mark_wire(mark) or None,
            )
            if attempt < options.retries:
                time.sleep(as_seconds(options.backoff) * (2 ** (attempt - 1)))
                continue
            raise last_error from exc
        except httpx.HTTPError as exc:
            last_error = TransportError(
                f"Mark document download failed: {exc}",
                PortoErrorCode.PORTO_NETWORK_UNAVAILABLE,
                status_code=503,
                details={"mark_id": mark.id, "url": mark.content},
                retryable=attempt < options.retries,
                provider=mark.provider,
                wire=mark_wire(mark) or None,
            )
            if attempt < options.retries:
                time.sleep(as_seconds(options.backoff) * (2 ** (attempt - 1)))
                continue
            raise last_error from exc

    if last_error is not None:
        raise last_error
    raise TransportError(
        "Mark document download failed",
        PortoErrorCode.PORTO_NETWORK_UNAVAILABLE,
        status_code=503,
        details={"mark_id": mark.id, "url": mark.content},
        retryable=False,
        provider=mark.provider,
        wire=mark_wire(mark) or None,
    )


async def fetch_mark_bytes(
    mark: PortoMark,
    *,
    http_client: Transport | None = None,
    retries: int = DEFAULT_MARK_FETCH_RETRIES,
    timeout: timedelta | float = DEFAULT_MARK_FETCH_TIMEOUT,
    backoff: timedelta | float = DEFAULT_MARK_FETCH_BACKOFF,
    normalize: Callable[[bytes], bytes] | None = None,
) -> bytes:
    """Download and normalize mark bytes from PortoMark.content."""
    options = FetchMarkBytesOptions(
        retries=retries,
        timeout=parse_duration(timeout),
        backoff=parse_duration(backoff),
    )
    payload = await _download_mark_payload(mark, http_client=http_client, options=options)
    return normalize_mark_document(mark, payload, normalize=normalize)


def fetch_mark_bytes_sync(
    mark: PortoMark,
    *,
    retries: int = DEFAULT_MARK_FETCH_RETRIES,
    timeout: timedelta | float = DEFAULT_MARK_FETCH_TIMEOUT,
    backoff: timedelta | float = DEFAULT_MARK_FETCH_BACKOFF,
    normalize: Callable[[bytes], bytes] | None = None,
) -> bytes:
    """Synchronous fetch_mark_bytes for scripts and offline tooling."""
    options = FetchMarkBytesOptions(
        retries=retries,
        timeout=parse_duration(timeout),
        backoff=parse_duration(backoff),
    )
    payload = _download_mark_payload_sync(mark, options=options)
    return normalize_mark_document(mark, payload, normalize=normalize)
