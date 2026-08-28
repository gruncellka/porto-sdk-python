"""One Internetmarke shopping-cart checkout: init → request → directCheckout."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from ....errors import PortoError, PortoErrorCode
from ....execution import ExecutionParameters
from .auth import InternetmarkeAuth
from .client import HttpJsonResult, InternetmarkeClient
from .error_mapper import InternetmarkeErrorMapper
from .positions import PdfPosition, PngPosition

logger = logging.getLogger(__name__)

_PROVIDER = "deutschepost"
_WIRE = "internetmarke"


@dataclass(frozen=True)
class CheckoutResult:
    shop_order_id: str
    link: str
    headers: Mapping[str, str]
    url: str
    request: Mapping[str, Any]
    response: Mapping[str, Any]

    def trace(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "request": dict(self.request),
            "response": dict(self.response),
            "response_headers": dict(self.headers),
        }


class InternetmarkeCheckout:
    """Orchestrates one provider checkout. Does not mint PortoMark."""

    def __init__(
        self,
        auth: InternetmarkeAuth,
        *,
        base_url: str | None = None,
        client: InternetmarkeClient | None = None,
        errors: InternetmarkeErrorMapper | None = None,
        http_client=None,
    ):
        self._auth = auth
        self._base_url = (base_url or auth.base_url).rstrip("/")
        self._client = client
        self._http_client = http_client
        self._errors = errors or InternetmarkeErrorMapper()

    async def png(
        self,
        *,
        positions: Sequence[PngPosition],
        total: int,
        execution: ExecutionParameters | None = None,
    ) -> CheckoutResult:
        if not positions:
            raise PortoError(
                "mark(many) requires at least one request",
                PortoErrorCode.PORTO_MARK_INVALID,
                status_code=400,
                provider=_PROVIDER,
                wire=_WIRE,
                retryable=False,
            )
        headers, client, request_id, idempotency_key = await self._session(execution)
        shop_order_id = await self._create_cart(client, headers, request_id, idempotency_key)
        body: dict[str, Any] = {
            "type": "AppShoppingCartPNGRequest",
            "shopOrderId": shop_order_id,
            "positions": [position.to_wire() for position in positions],
            "total": total,
            "createManifest": True,
            "dpi": "DPI300",
            "optimizePNG": True,
        }
        url = f"{client.base_url}/app/shoppingcart/png?directCheckout=true"
        return await self._checkout(
            lambda: client.checkout_png(body, headers=headers, idempotency_key=idempotency_key),
            body=body,
            url=url,
            shop_order_id=shop_order_id,
            request_id=request_id,
            product_code=positions[0].product_code,
        )

    async def pdf(
        self,
        *,
        positions: Sequence[PdfPosition],
        total: int,
        execution: ExecutionParameters | None = None,
        page_format_id: int = 2,
    ) -> CheckoutResult:
        if not positions:
            raise PortoError(
                "mark(many) requires at least one request",
                PortoErrorCode.PORTO_MARK_INVALID,
                status_code=400,
                provider=_PROVIDER,
                wire=_WIRE,
                retryable=False,
            )
        headers, client, request_id, idempotency_key = await self._session(execution)
        shop_order_id = await self._create_cart(client, headers, request_id, idempotency_key)
        body: dict[str, Any] = {
            "type": "AppShoppingCartPDFRequest",
            "shopOrderId": shop_order_id,
            "pageFormatId": page_format_id,
            "positions": [position.to_wire() for position in positions],
            "total": total,
            "createManifest": True,
            "dpi": "DPI300",
        }
        url = f"{client.base_url}/app/shoppingcart/pdf?directCheckout=true"
        return await self._checkout(
            lambda: client.checkout_pdf(body, headers=headers, idempotency_key=idempotency_key),
            body=body,
            url=url,
            shop_order_id=shop_order_id,
            request_id=request_id,
            product_code=positions[0].product_code,
        )

    async def _session(
        self, execution: ExecutionParameters | None
    ) -> tuple[dict[str, str], InternetmarkeClient, str, str | None]:
        await self._auth.authenticate()
        http_client = self._http_client or self._auth.get_http_client()
        if not http_client:
            raise PortoError(
                "HTTP client not available",
                PortoErrorCode.PORTO_NETWORK_UNAVAILABLE,
                status_code=503,
                provider=_PROVIDER,
                wire=_WIRE,
                retryable=False,
            )
        token = self._auth.get_token()
        if not token:
            raise PortoError(
                "Not authenticated",
                PortoErrorCode.PORTO_AUTH_FAILED,
                status_code=401,
                provider=_PROVIDER,
                wire=_WIRE,
                retryable=False,
            )
        request_id = (execution.request_id if execution else None) or ""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Request-ID": request_id,
        }
        client = self._client or InternetmarkeClient(self._base_url, http_client)
        idempotency_key = execution.idempotency_key if execution else None
        return headers, client, request_id, idempotency_key

    async def _create_cart(
        self,
        client: InternetmarkeClient,
        headers: Mapping[str, str],
        request_id: str,
        idempotency_key: str | None,
    ) -> str:
        try:
            init = await client.create_cart(headers=headers, idempotency_key=idempotency_key)
        except PortoError:
            raise
        except httpx.HTTPError as exc:
            raise self._errors.network(exc, request_id=request_id) from exc
        self._errors.raise_if_init_failed(init, request_id=request_id)
        payload = init.json_data if isinstance(init.json_data, dict) else {}
        shop_order_id = payload.get("shopOrderId")
        if not shop_order_id:
            raise PortoError(
                "shopOrderId not in init response",
                PortoErrorCode.PORTO_MARK_FAILED,
                status_code=500,
                details={"response": payload, "requestId": request_id},
                provider=_PROVIDER,
                wire=_WIRE,
                retryable=False,
            )
        return str(shop_order_id)

    async def _checkout(
        self,
        send: Callable[[], Awaitable[HttpJsonResult]],
        *,
        body: Mapping[str, Any],
        url: str,
        shop_order_id: str,
        request_id: str,
        product_code: int,
    ) -> CheckoutResult:
        logger.debug("Calling REST shopping-cart directCheckout: %s", url)
        try:
            result = await send()
        except PortoError:
            raise
        except httpx.HTTPError as exc:
            raise self._errors.network(exc, request_id=request_id) from exc
        self._errors.raise_if_checkout_failed(
            result,
            request_id=request_id,
            product_code=product_code,
            body=body,
        )
        payload = result.json_data if isinstance(result.json_data, dict) else {}
        external_id = str(payload.get("shopOrderId") or shop_order_id) or shop_order_id
        return CheckoutResult(
            shop_order_id=external_id,
            link=str(payload.get("link") or ""),
            headers=dict(result.headers),
            url=url,
            request=dict(body),
            response=payload,
        )
