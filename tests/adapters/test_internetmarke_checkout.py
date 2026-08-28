"""Internetmarke checkout orchestration (init + directCheckout)."""

from pathlib import Path

import pytest

from porto_sdk.adapters.deutschepost.internetmarke import checkout as checkout_module
from porto_sdk.adapters.deutschepost.internetmarke.checkout import InternetmarkeCheckout
from porto_sdk.adapters.deutschepost.internetmarke.positions import PositionFactory, PositionMark
from porto_sdk.execution import ExecutionParameters


def test_png_shoppingcart_body_uses_optimize_png_casing() -> None:
    source = Path(checkout_module.__file__).read_text(encoding="utf-8")
    assert '"optimizePNG"' in source or "'optimizePNG'" in source
    assert "optimizePng" not in source.replace("optimizePNG", "")


class _FakeHttpClient:
    def __init__(self):
        self.calls = []

    async def request(self, **kwargs):
        self.calls.append(kwargs)
        url = kwargs.get("url", "")

        class _Resp:
            is_success = True
            status_code = 200
            headers = {}
            text = "{}"

            @staticmethod
            def json():
                if "shoppingcart/png" in url:
                    return {
                        "shopOrderId": "order-1",
                        "link": "https://example.test/stamp.png",
                    }
                return {"shopOrderId": "order-1"}

        return _Resp()


class _FakeAuth:
    def __init__(self):
        self.http = _FakeHttpClient()

    async def authenticate(self) -> None:
        return None

    def get_http_client(self):
        return self.http

    def get_token(self) -> str:
        return "token"


@pytest.mark.asyncio
async def test_checkout_passes_idempotency_key() -> None:
    auth = _FakeAuth()
    checkout = InternetmarkeCheckout(auth, base_url="https://example.test")
    result = await checkout.png(
        positions=[PositionFactory().png(PositionMark(product_code=1))],
        total=100,
        execution=ExecutionParameters(request_id="o1", idempotency_key="idmp-1"),
    )
    assert result.shop_order_id == "order-1"
    assert result.link == "https://example.test/stamp.png"
    assert len(auth.http.calls) == 2
    assert auth.http.calls[0]["idempotency_key"] == "idmp-1"
    assert auth.http.calls[0]["headers"]["X-Request-ID"] == "o1"


@pytest.mark.asyncio
async def test_png_cart_one_checkout_three_positions() -> None:
    auth = _FakeAuth()
    checkout = InternetmarkeCheckout(auth, base_url="https://example.test")
    factory = PositionFactory()
    result = await checkout.png(
        positions=[
            factory.png(PositionMark(product_code=21)),
            factory.png(PositionMark(product_code=21)),
            factory.png(PositionMark(product_code=21)),
        ],
        total=285,
        execution=ExecutionParameters(request_id="cart-1", idempotency_key="idmp-cart"),
    )
    init_calls = [
        call for call in auth.http.calls if str(call.get("url", "")).endswith("/shoppingcart")
    ]
    png_calls = [call for call in auth.http.calls if "shoppingcart/png" in str(call.get("url", ""))]
    assert len(init_calls) == 1
    assert len(png_calls) == 1
    body = png_calls[0]["json"]
    assert len(body["positions"]) == 3
    assert body["total"] == 285
    assert result.shop_order_id == "order-1"
    assert result.link == "https://example.test/stamp.png"
    assert len(result.request["positions"]) == 3
