"""ACL, wire resolution, and Deutsche Post shipment tracking."""

from __future__ import annotations

import json

import httpx
import pytest

from porto_sdk.adapters.deutschepost.internetmarke.adapter import InternetmarkeAdapter
from porto_sdk.adapters.deutschepost.tracking.shipment import Adapter as Shipment
from porto_sdk.adapters.tracking.acl import STATUS_MAPS, map_native_status
from porto_sdk.adapters.tracking.adapter import (
    StubTrackingAdapter,
    UnsupportedTrackingAdapter,
    get_tracking_adapter,
    map_event,
)
from porto_sdk.config import WireConfig
from porto_sdk.errors import PortoError, PortoErrorCode
from porto_sdk.execution import PortoMark
from porto_sdk.provider_payload import sanitize_provider_payload
from porto_sdk.types import PortoStatus

CHECKOUT = {
    "shopOrderId": "order-1",
    "link": "https://example.test/mark.pdf",
    "accessToken": "secret-token",
    "voucherList": [{"voucherId": "v-1"}],
}

CHECKOUT_TRACKED = {
    "shopOrderId": "order-2",
    "link": "https://example.test/mark.pdf",
    "voucherList": [
        {"voucherId": "v-1", "trackId": "TRACK1"},
        {"voucherId": "v-2", "trackId": "TRACK2"},
    ],
}


@pytest.mark.parametrize("provider", sorted(STATUS_MAPS))
def test_each_provider_map_covers_every_porto_status(provider: str) -> None:
    mapped = {map_native_status(provider, key) for key in STATUS_MAPS[provider]}
    assert mapped == set(PortoStatus)


def test_unknown_native_code_stays_null() -> None:
    assert map_native_status("deutschepost", "not-a-real-dp-code") is None
    event = map_event(
        provider_id="deutschepost",
        tracking_number="AB",
        native_code="not-a-real-dp-code",
        native_label="mystery",
        occurred_at="2026-01-01T00:00:00+00:00",
        received_at="2026-01-01T00:00:01+00:00",
    )
    assert event.status is None
    assert event.provider_code == "not-a-real-dp-code"
    assert event.status != PortoStatus.TRANSIT
    assert not hasattr(PortoStatus, "UNKNOWN")


def test_dp_pre_transit_maps_to_created() -> None:
    event = map_event(
        provider_id="deutschepost",
        tracking_number="AB",
        native_code="pre-transit",
        native_label="Announced",
        occurred_at="2026-01-01T00:00:00+00:00",
        received_at="2026-01-01T00:00:01+00:00",
    )
    assert event.status is PortoStatus.CREATED
    assert event.provider_code == "pre-transit"
    assert event.provider_label == "Announced"


def test_tracking_wire_resolution() -> None:
    stamp = get_tracking_adapter("deutschepost", wire_id="internetmarke")
    assert isinstance(stamp, UnsupportedTrackingAdapter)
    assert stamp.wire == "internetmarke"

    missing = get_tracking_adapter("deutschepost", wire_id="")
    assert isinstance(missing, UnsupportedTrackingAdapter)

    blank = get_tracking_adapter("deutschepost", wire_id="shipment", base_url="  ")
    assert isinstance(blank, UnsupportedTrackingAdapter)

    live = get_tracking_adapter(
        "deutschepost",
        wire_id="shipment",
        base_url="https://track.example",
        http_client=object(),
    )
    assert isinstance(live, Shipment)

    other = get_tracking_adapter("laposte", wire_id="shipment", base_url="https://track.example")
    assert isinstance(other, StubTrackingAdapter)

    from porto_sdk.adapters.tracking.adapter import tracking_wire_id

    assert tracking_wire_id(None) is None
    assert tracking_wire_id({"internetmarke": WireConfig()}) is None
    assert tracking_wire_id({"shipment": WireConfig(base_url="")}) is None
    assert (
        tracking_wire_id({"shipment": WireConfig(base_url="https://track.example")}) == "shipment"
    )


def test_sanitize_drops_secrets() -> None:
    cleaned = sanitize_provider_payload(
        {"shopOrderId": "o", "accessToken": "nope", "nested": [{"api_key": "x"}]}
    )
    assert cleaned == {"shopOrderId": "o", "nested": [{}]}


class _Transport:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    async def request(self, **kwargs):
        self.kwargs = kwargs
        return self.response


@pytest.mark.asyncio
async def test_dp_shipment_adapter_maps_events() -> None:
    body = {
        "events": [
            {
                "code": "pre-transit",
                "label": "Announced",
                "timestamp": "2026-01-01T00:00:00Z",
                "token": "drop-me",
            },
            {
                "code": "not-a-real-dp-code",
                "label": "Mystery",
                "timestamp": "2026-01-02T00:00:00Z",
            },
        ]
    }
    response = httpx.Response(200, json=body)
    transport = _Transport(response)
    adapter = Shipment(
        base_url="https://track.example/",
        http_client=transport,
    )
    snapshot = await adapter.track("AB 1")
    assert snapshot.status is PortoStatus.CREATED
    assert snapshot.history[0].status is PortoStatus.CREATED
    assert snapshot.history[1].status is None
    assert snapshot.history[1].provider_code == "not-a-real-dp-code"
    assert snapshot.provider_raw is not None
    assert "token" not in json.dumps(snapshot.provider_raw)
    assert "AB%201" in transport.kwargs["url"]


@pytest.mark.asyncio
async def test_dp_shipment_adapter_errors() -> None:
    adapter = Shipment(base_url="https://track.example", http_client=None)
    with pytest.raises(PortoError) as missing:
        await adapter.track("AB")
    assert missing.value.code is PortoErrorCode.PORTO_NETWORK_UNAVAILABLE

    not_found = Shipment(
        base_url="https://track.example",
        http_client=_Transport(httpx.Response(404, json={})),
    )
    with pytest.raises(PortoError) as lost:
        await not_found.track("AB")
    assert lost.value.code is PortoErrorCode.PORTO_TRACKING_NOT_FOUND

    broken = Shipment(
        base_url="https://track.example",
        http_client=_Transport(httpx.Response(200, json=["nope"])),
    )
    with pytest.raises(PortoError) as bad:
        await broken.track("AB")
    assert bad.value.code is PortoErrorCode.PORTO_NETWORK_UNAVAILABLE


def test_mark_checkout_does_not_invent_created() -> None:
    assert "status" not in PortoMark.model_fields
    adapter = InternetmarkeAdapter.__new__(InternetmarkeAdapter)
    adapter.provider_id = "deutschepost"
    adapter.wire_id = "internetmarke"

    class Result:
        shop_order_id = CHECKOUT["shopOrderId"]
        link = CHECKOUT["link"]
        response = CHECKOUT

    mark = adapter._marks_from_checkout(Result(), "image/png", [95])[0]
    assert mark.external_id == "order-1"
    assert mark.tracking_number is None
    assert mark.provider_raw is not None
    assert mark.provider_raw["voucherList"][0]["voucherId"] == "v-1"
    assert "accessToken" not in mark.provider_raw
    assert PortoStatus.CREATED.value not in mark.model_dump()

    class Tracked:
        shop_order_id = CHECKOUT_TRACKED["shopOrderId"]
        link = CHECKOUT_TRACKED["link"]
        response = CHECKOUT_TRACKED

    marks = adapter._marks_from_checkout(Tracked(), "application/pdf", [95, 110])
    assert [item.tracking_number for item in marks] == ["TRACK1", "TRACK2"]
    assert marks[0].provider_raw["voucherIndex"] == 0
    assert marks[1].external_id == "order-2"
    assert all(
        "status" not in item.model_dump() or item.model_dump().get("status") is None
        for item in marks
    )


@pytest.mark.asyncio
async def test_track_stamp_delegates_to_unsupported() -> None:
    adapter = InternetmarkeAdapter.__new__(InternetmarkeAdapter)
    adapter.provider_id = "deutschepost"
    with pytest.warns(DeprecationWarning):
        with pytest.raises(PortoError) as exc:
            await adapter.track_stamp("AB")
    assert exc.value.code is PortoErrorCode.PORTO_TRACKING_UNSUPPORTED
    assert exc.value.details["wire"] == "internetmarke"
