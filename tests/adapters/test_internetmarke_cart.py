"""Internetmarke mark(many): any mix, order preserved, provider reject → mark failed."""

from __future__ import annotations

import pytest

from porto_sdk.adapters.deutschepost.internetmarke.adapter import InternetmarkeAdapter
from porto_sdk.errors import PortoError, PortoErrorCode
from porto_sdk.execution import PortoMarkRequest
from porto_sdk.requires import RECIPIENT
from tests.support.addresses import licko_recipient, licko_sender
from tests.support.bound_provider import bound_provider

DE_SENDER = licko_sender()
DE_RECIPIENT = licko_recipient("DE")


def _im_execution(client, adapter):
    adapter.set_country_code_3_lookup(client.jurisdictions.country_code_3)
    execution = bound_provider(client)._execution
    execution.adapter = adapter
    return execution


def _resolve(client, *, weight: int = 20):
    return bound_provider(client).resolve(country_code="DE", weight=weight)


class _CartHttp:
    def __init__(self, *, fail_png: bool = False) -> None:
        self.calls: list[dict] = []
        self.fail_png = fail_png

    async def request(self, **kwargs):
        self.calls.append(kwargs)
        url = str(kwargs.get("url") or "")

        class _Resp:
            is_success = True
            status_code = 200
            headers = {"content-type": "application/json"}
            text = "{}"

            @staticmethod
            def json():
                if url.rstrip("/").endswith("/user"):
                    return {"access_token": "token", "expires_in": 3000}
                if url.rstrip("/").endswith("/shoppingcart"):
                    return {"shopOrderId": "order-1"}
                return {
                    "shopOrderId": "order-1",
                    "link": "https://example.test/cart.zip",
                    "voucherList": [{"shopOrderId": "order-1"}],
                }

        if self.fail_png and "shoppingcart/png" in url:
            class _Fail:
                is_success = False
                status_code = 500
                headers = {"content-type": "application/json"}
                text = '{"message":"cart rejected"}'

                @staticmethod
                def json():
                    return {"message": "cart rejected"}

            return _Fail()
        return _Resp()


@pytest.mark.offline
@pytest.mark.asyncio
async def test_im_empty_many_invalid(client) -> None:
    adapter = InternetmarkeAdapter(
        username="user",
        password="pass",
        api_key="key",
        api_secret="secret",
    )
    execution = _im_execution(client, adapter)
    with pytest.raises(PortoError) as exc:
        await execution.mark([])
    assert exc.value.code == PortoErrorCode.PORTO_MARK_INVALID


@pytest.mark.offline
@pytest.mark.asyncio
async def test_im_heterogeneous_many_preserves_order(client) -> None:
    light = _resolve(client, weight=20)
    heavy = _resolve(client, weight=400)
    http = _CartHttp()
    adapter = InternetmarkeAdapter(
        username="user",
        password="pass",
        api_key="key",
        api_secret="secret",
        http_client=http,
    )
    execution = _im_execution(client, adapter)
    marks = await execution.mark(
        [
            PortoMarkRequest(porto=light),
            PortoMarkRequest(porto=heavy),
            PortoMarkRequest(porto=light),
        ]
    )
    assert [mark.amount for mark in marks] == [light.amount, heavy.amount, light.amount]
    png_calls = [call for call in http.calls if "shoppingcart/png" in str(call.get("url", ""))]
    assert len(png_calls) == 1
    body = png_calls[0]["json"]
    assert len(body["positions"]) == 3
    assert body["total"] == light.amount * 2 + heavy.amount
    assert adapter.last_many_trace is not None
    assert len(adapter.last_many_trace["request"]["positions"]) == 3


@pytest.mark.offline
@pytest.mark.asyncio
async def test_im_address_bearing_many_allowed(client) -> None:
    porto = _resolve(client).model_copy(update={"requires": frozenset({RECIPIENT})})
    http = _CartHttp()
    adapter = InternetmarkeAdapter(
        username="user",
        password="pass",
        api_key="key",
        api_secret="secret",
        http_client=http,
    )
    execution = _im_execution(client, adapter)
    marks = await execution.mark(
        [
            PortoMarkRequest(porto=porto, sender=DE_SENDER, recipient=DE_RECIPIENT),
            PortoMarkRequest(porto=porto, sender=DE_SENDER, recipient=DE_RECIPIENT),
        ]
    )
    assert len(marks) == 2
    png_calls = [call for call in http.calls if "shoppingcart/png" in str(call.get("url", ""))]
    assert len(png_calls) == 1
    assert len(png_calls[0]["json"]["positions"]) == 2


@pytest.mark.offline
@pytest.mark.asyncio
async def test_im_provider_cart_failure_is_mark_failed(client) -> None:
    porto = _resolve(client)
    http = _CartHttp(fail_png=True)
    adapter = InternetmarkeAdapter(
        username="user",
        password="pass",
        api_key="key",
        api_secret="secret",
        http_client=http,
    )
    execution = _im_execution(client, adapter)
    with pytest.raises(PortoError) as exc:
        await execution.mark([PortoMarkRequest(porto=porto), PortoMarkRequest(porto=porto)])
    assert exc.value.code in {
        PortoErrorCode.PORTO_MARK_FAILED,
        PortoErrorCode.PORTO_NETWORK_UNAVAILABLE,
    }


@pytest.mark.offline
@pytest.mark.asyncio
async def test_im_homogeneous_three_stamps_one_png_checkout(client) -> None:
    porto = _resolve(client)
    http = _CartHttp()
    adapter = InternetmarkeAdapter(
        username="user",
        password="pass",
        api_key="key",
        api_secret="secret",
        http_client=http,
    )
    execution = _im_execution(client, adapter)
    marks = await execution.mark(
        [
            PortoMarkRequest(porto=porto),
            PortoMarkRequest(porto=porto),
            PortoMarkRequest(porto=porto),
        ]
    )
    init_calls = [call for call in http.calls if str(call.get("url", "")).endswith("/shoppingcart")]
    png_calls = [call for call in http.calls if "shoppingcart/png" in str(call.get("url", ""))]
    assert len(init_calls) == 1
    assert len(png_calls) == 1
    body = png_calls[0]["json"]
    assert len(body["positions"]) == 3
    assert body["total"] == porto.amount * 3
    assert {mark.external_id for mark in marks} == {"order-1"}
    assert len({mark.id for mark in marks}) == 3
