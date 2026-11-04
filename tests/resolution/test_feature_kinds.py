"""Purchased feature kinds on Porto, ServiceOption, and PortoMark."""

from __future__ import annotations

import pytest

from porto_sdk import PROOF_FEATURE_KINDS
from porto_sdk.adapters.deutschepost.internetmarke.adapter import InternetmarkeAdapter
from porto_sdk.adapters.deutschepost.internetmarke.checkout import CheckoutResult
from porto_sdk.config import CacheConfig
from porto_sdk.data.context import PostalResolutionContext
from porto_sdk.data.domain_validator import DomainIds
from porto_sdk.data.loader import PortoDataLoader
from porto_sdk.errors import PortoError, PortoErrorCode
from porto_sdk.execution import ExecutionParameters, MarkExecution, build_porto_mark
from porto_sdk.services.feature_kinds import feature_kinds_for_service_ids
from porto_sdk.services.porto_execution import PortoExecution
from porto_sdk.services.porto_resolver import PortoResolver, ResolutionRequest
from porto_sdk.types import MarkRequest, TrackingStatus

_ROWS = {
    None: [],
    "einschreiben": ["tracking", "acceptance_proof"],
    "einschreiben_einwurf": ["tracking"],
    "einschreiben_rueckschein": [
        "tracking",
        "recipient_signature",
        "return_receipt",
        "delivery_proof",
    ],
}
_KINDS = {
    "einschreiben": "registered",
    "einschreiben_einwurf": "registered",
    "einschreiben_rueckschein": "registered_return_receipt",
}


def _resolver(porto_data_path: str) -> PortoResolver:
    loader = PortoDataLoader(
        porto_data_path,
        provider="deutschepost",
        verify_checksums=False,
        strict_mode=False,
    )
    validator = DomainIds(loader)
    ctx = PostalResolutionContext(loader=loader, provider_id="deutschepost")
    return PortoResolver(ctx, validator, CacheConfig(enabled=False))


def _resolve(resolver: PortoResolver, service_id: str | None = None):
    kwargs: dict = {"country_code": "DE", "weight": 20, "product_id": "standardbrief"}
    if service_id is not None:
        kwargs["service_ids"] = [service_id]
        kwargs["services"] = [_KINDS[service_id]]
    return resolver.resolve(ResolutionRequest(**kwargs))


class _MissingFeature:
    def get_service(self, service_id: str):
        if service_id == "einschreiben":
            return type("Service", (), {"features": ("missing_feature",)})()
        return None

    def get_feature(self, feature_id: str):
        del feature_id
        return None


class _DuplicateKinds:
    def get_service(self, service_id: str):
        return type("Service", (), {"features": ("sendungsnummer",)})()

    def get_feature(self, feature_id: str):
        del feature_id
        return type("Feature", (), {"kind": "tracking"})()


class _Adapter:
    async def mark(self, request, *, resolved_product, execution):
        del request, resolved_product, execution
        return build_porto_mark(
            provider="deutschepost",
            wire="internetmarke",
            content="mark",
            content_type="image/png",
            amount=1,
            tracking_number="RR123",
        )


@pytest.mark.offline
def test_catalog_rows(porto_data_path: str) -> None:
    resolver = _resolver(porto_data_path)
    plain = _resolve(resolver)
    bought = _resolve(resolver, "einschreiben")
    assert list(plain.feature_kinds) == []
    assert [row.id for row in plain.features] == [row.id for row in bought.features]
    for service_id, expected in _ROWS.items():
        if service_id is None:
            continue
        assert list(_resolve(resolver, service_id).feature_kinds) == expected


@pytest.mark.offline
def test_options_list_kinds_before_purchase(porto_data_path: str) -> None:
    resolver = _resolver(porto_data_path)
    zone_id = _resolve(resolver).zone.id
    options = resolver.catalog.list_service_options_for_product_zone("standardbrief", zone_id)
    by_id = {row.id: list(row.feature_kinds) for row in options}
    for service_id, expected in _ROWS.items():
        if service_id is None:
            continue
        assert by_id[service_id] == expected


def test_missing_feature_id_fails_closed() -> None:
    with pytest.raises(PortoError) as exc:
        feature_kinds_for_service_ids(_MissingFeature(), ["einschreiben"])
    assert exc.value.code == PortoErrorCode.PORTO_DATA_INVALID
    assert exc.value.details["service_id"] == "einschreiben"
    assert exc.value.details["feature_id"] == "missing_feature"


def test_duplicate_kinds_collapse() -> None:
    kinds = feature_kinds_for_service_ids(
        _DuplicateKinds(), ["einschreiben", "einschreiben_einwurf"]
    )
    assert kinds == ["tracking"]


def test_proof_subset_excludes_tracking() -> None:
    assert "tracking" not in PROOF_FEATURE_KINDS
    assert "feature_kinds" not in TrackingStatus.model_fields


def test_new_mark_leaves_feature_kinds_empty() -> None:
    mark = build_porto_mark(
        provider="deutschepost",
        wire="internetmarke",
        content="mark",
        content_type="image/png",
        amount=1,
        tracking_number="RR123",
    )
    assert mark.feature_kinds == []
    assert mark.tracking_number == "RR123"


@pytest.mark.asyncio
@pytest.mark.offline
async def test_execute_copies_feature_kinds(porto_data_path: str) -> None:
    resolver = _resolver(porto_data_path)
    execution = PortoExecution(resolver.data_loader, adapter=_Adapter())
    plain = _resolve(resolver)
    bought = _resolve(resolver, "einschreiben_rueckschein")
    for porto in (plain, bought):
        prepared = MarkExecution(
            porto=porto,
            request=MarkRequest(value=porto.amount),
            resolved_product=porto.product,
        )
        mark = await execution.execute(prepared, 0)
        assert mark.tracking_number == "RR123"
        assert list(mark.feature_kinds) == list(porto.feature_kinds)


_DP_CHECKOUT = {
    "shopOrderId": "order-9",
    "link": "https://example.test/mark.png",
    "voucherList": [{"voucherId": "v-9", "trackId": "A0031B2C3D"}],
}


class _DpCheckout:
    async def png(self, *, positions, total, execution):
        del positions, execution
        return CheckoutResult(
            shop_order_id="order-9",
            link="https://example.test/mark.png",
            headers={},
            url="https://api-eu.dhl.com/post/de/shipping/im/v1/app/shoppingcart/png",
            request={"total": total},
            response=_DP_CHECKOUT,
        )


@pytest.mark.asyncio
@pytest.mark.offline
async def test_internetmarke_checkout_keeps_track_id_and_copies_kinds(porto_data_path: str) -> None:
    resolver = _resolver(porto_data_path)
    adapter = InternetmarkeAdapter()
    adapter._checkout_for = lambda execution: _DpCheckout()  # type: ignore[method-assign]
    execution = PortoExecution(resolver.data_loader, adapter=adapter)
    request = MarkRequest(value=95, wire_code=1, zone="domestic")
    for service_id in (None, "einschreiben_rueckschein"):
        porto = _resolve(resolver, service_id)
        direct = await adapter.mark(
            request,
            resolved_product=porto.product,
            execution=ExecutionParameters(),
        )
        assert direct.tracking_number == "A0031B2C3D"
        assert direct.feature_kinds == []
        prepared = MarkExecution(
            porto=porto,
            request=request,
            resolved_product=porto.product,
        )
        copied = await execution.execute(prepared, 0)
        assert copied.tracking_number == "A0031B2C3D"
        assert list(copied.feature_kinds) == list(porto.feature_kinds)
        assert "feature_kinds" not in _DP_CHECKOUT
