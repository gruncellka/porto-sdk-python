"""Dumb Internetmarke HTTP client — POST JSON, return status/body/headers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ....transport.http_client import Transport


@dataclass(frozen=True)
class HttpJsonResult:
    status_code: int
    ok: bool
    text: str
    headers: Mapping[str, str]
    json_data: Any

    @classmethod
    def from_response(cls, resp: Any) -> HttpJsonResult:
        status = int(getattr(resp, "status_code", getattr(resp, "status", 0)) or 0)
        ok = getattr(resp, "is_success", None)
        if ok is None:
            ok = 200 <= status < 300
        text = str(getattr(resp, "text", "") or "")
        raw_headers = getattr(resp, "headers", None) or {}
        try:
            headers = {str(key): str(value) for key, value in raw_headers.items()}
        except Exception:
            headers = {}
        json_data: Any = None
        parser = getattr(resp, "json", None)
        if callable(parser):
            try:
                json_data = parser()
            except Exception:
                json_data = None
        return cls(
            status_code=status,
            ok=bool(ok),
            text=text,
            headers=headers,
            json_data=json_data,
        )


class InternetmarkeClient:
    """Shopping-cart HTTP surface. No PortoMark, no voucherLayout, no traces."""

    def __init__(self, base_url: str, http_client: Transport):
        self.base_url = base_url.rstrip("/")
        self._http = http_client

    async def create_cart(
        self,
        *,
        headers: Mapping[str, str],
        idempotency_key: str | None = None,
    ) -> HttpJsonResult:
        return await self._post(
            f"{self.base_url}/app/shoppingcart",
            {},
            headers=headers,
            idempotency_key=idempotency_key,
        )

    async def checkout_png(
        self,
        body: Mapping[str, Any],
        *,
        headers: Mapping[str, str],
        idempotency_key: str | None = None,
    ) -> HttpJsonResult:
        return await self._post(
            f"{self.base_url}/app/shoppingcart/png?directCheckout=true",
            body,
            headers=headers,
            idempotency_key=idempotency_key,
        )

    async def checkout_pdf(
        self,
        body: Mapping[str, Any],
        *,
        headers: Mapping[str, str],
        idempotency_key: str | None = None,
    ) -> HttpJsonResult:
        return await self._post(
            f"{self.base_url}/app/shoppingcart/pdf?directCheckout=true",
            body,
            headers=headers,
            idempotency_key=idempotency_key,
        )

    async def _post(
        self,
        url: str,
        body: Mapping[str, Any],
        *,
        headers: Mapping[str, str],
        idempotency_key: str | None,
    ) -> HttpJsonResult:
        resp = await self._http.request(
            method="POST",
            url=url,
            json=dict(body),
            headers=dict(headers),
            idempotent=False,
            idempotency_key=idempotency_key,
        )
        return HttpJsonResult.from_response(resp)
