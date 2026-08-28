"""
HTTP transport with timeout, retry, and header policy.
"""

from __future__ import annotations

import asyncio
import platform
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol

import httpx

from ..config import TransportConfig
from ..errors import PortoErrorCode, TransportError
from ..time import as_seconds, parse_duration

DEFAULT_TIMEOUT = TransportConfig().timeout
DEFAULT_MAX_RETRIES = TransportConfig().retries
DEFAULT_BACKOFF = TransportConfig().backoff


def _sdk_version() -> str:
    try:
        from importlib.metadata import version

        return version("gruncellka-porto-sdk")
    except Exception:
        return "0.0.0"


def build_user_agent() -> str:
    return f"gruncellka-porto-sdk/{_sdk_version()} (python/{platform.python_version()})"


class Transport(Protocol):
    """HTTP request seam used by adapters and PortoClient."""

    async def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json: Any = None,
        data: Any = None,
        idempotent: bool = True,
        idempotency_key: str | None = None,
    ) -> httpx.Response: ...

    async def close(self) -> None: ...


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff: timedelta = DEFAULT_BACKOFF


class HttpClient:
    def __init__(
        self,
        timeout: timedelta | float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_MAX_RETRIES,
        backoff: timedelta | float = DEFAULT_BACKOFF,
    ) -> None:
        self.timeout = parse_duration(timeout)
        self.retry_policy = RetryPolicy(max_retries=retries, backoff=parse_duration(backoff))
        self._client = httpx.AsyncClient(timeout=as_seconds(self.timeout))

    async def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json: Any = None,
        data: Any = None,
        idempotent: bool = True,
        idempotency_key: str | None = None,
    ) -> httpx.Response:
        attempts = self.retry_policy.max_retries if (idempotent or idempotency_key) else 1
        merged_headers = {
            "User-Agent": build_user_agent(),
            **(headers or {}),
        }
        if json is not None:
            merged_headers.setdefault("Content-Type", "application/json")
        if idempotency_key:
            merged_headers.setdefault("Idempotency-Key", idempotency_key)

        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    headers=merged_headers,
                    json=json,
                    data=data,
                )
                if response.status_code >= 500 and attempt < attempts:
                    await asyncio.sleep(
                        as_seconds(self.retry_policy.backoff * (2 ** (attempt - 1)))
                    )
                    continue
                return response
            except httpx.TimeoutException as exc:
                last_error = TransportError(
                    "Request timed out",
                    PortoErrorCode.PORTO_NETWORK_TIMEOUT,
                    status_code=408,
                    details={"url": url, "method": method},
                    retryable=attempt < attempts,
                )
                if attempt < attempts:
                    await asyncio.sleep(
                        as_seconds(self.retry_policy.backoff * (2 ** (attempt - 1)))
                    )
                    continue
                raise last_error from exc
            except httpx.HTTPError as exc:
                last_error = TransportError(
                    f"Network error: {exc}",
                    PortoErrorCode.PORTO_NETWORK_UNAVAILABLE,
                    status_code=503,
                    details={"url": url, "method": method},
                    retryable=attempt < attempts,
                )
                if attempt < attempts:
                    await asyncio.sleep(
                        as_seconds(self.retry_policy.backoff * (2 ** (attempt - 1)))
                    )
                    continue
                raise last_error from exc

        if last_error is not None:
            raise last_error
        raise TransportError(
            "Unknown transport error",
            PortoErrorCode.PORTO_NETWORK_UNAVAILABLE,
            status_code=503,
            details={"url": url, "method": method},
            retryable=False,
        )

    async def close(self) -> None:
        await self._client.aclose()
