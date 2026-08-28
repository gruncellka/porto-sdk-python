"""Per-call credentials and optional wire pin on a cached ProviderClient."""

from __future__ import annotations

import asyncio

import pytest

from porto_sdk.errors import PortoError, PortoErrorCode
from porto_sdk.execution import ExecutionParameters, PortoMarkRequest, build_porto_mark
from tests.support.bound_provider import bound_provider


class _CaptureAdapter:
    def __init__(self) -> None:
        self.calls: list[dict[str, str] | None] = []

    @property
    def provider_id(self) -> str:
        return "deutschepost"

    @property
    def wire_id(self) -> str:
        return "internetmarke"

    async def mark(self, request, resolved_product=None, execution=None):
        creds = dict(execution.credentials) if execution and execution.credentials else None
        self.calls.append(creds)
        return build_porto_mark(
            provider="deutschepost",
            wire="internetmarke",
            content="https://example.test/mark.png",
            content_type="image/png",
            amount=request.value,
        )


def _install(client) -> tuple[object, _CaptureAdapter]:
    provider = bound_provider(client)
    adapter = _CaptureAdapter()
    provider._execution.adapter = adapter
    return provider, adapter


@pytest.mark.offline
@pytest.mark.asyncio
async def test_sequential_mark_credentials_are_independent(client) -> None:
    provider, adapter = _install(client)
    porto = provider.resolve(country_code="DE", weight=20)
    creds_a = {"username": "user-a", "password": "secret-a"}
    creds_b = {"username": "user-b", "password": "secret-b"}
    await provider.mark(
        PortoMarkRequest(porto=porto),
        ExecutionParameters(credentials=creds_a),
    )
    await provider.mark(
        PortoMarkRequest(porto=porto),
        ExecutionParameters(credentials=creds_b),
    )
    assert adapter.calls == [creds_a, creds_b]
    assert provider.provider_id == "deutschepost"
    assert provider._execution.adapter is adapter


@pytest.mark.offline
@pytest.mark.asyncio
async def test_concurrent_mark_credentials_are_independent(client) -> None:
    provider, adapter = _install(client)
    porto = provider.resolve(country_code="DE", weight=20)
    creds_a = {"username": "user-a", "password": "secret-a"}
    creds_b = {"username": "user-b", "password": "secret-b"}
    await asyncio.gather(
        provider.mark(
            PortoMarkRequest(porto=porto),
            ExecutionParameters(credentials=creds_a),
        ),
        provider.mark(
            PortoMarkRequest(porto=porto),
            ExecutionParameters(credentials=creds_b),
        ),
    )
    assert {tuple(sorted(row.items())) for row in adapter.calls if row} == {
        tuple(sorted(creds_a.items())),
        tuple(sorted(creds_b.items())),
    }
    assert provider._execution.adapter is adapter


@pytest.mark.offline
@pytest.mark.asyncio
async def test_omitted_wire_selects_internetmarke(client) -> None:
    provider, _adapter = _install(client)
    porto = provider.resolve(country_code="DE", weight=20)
    mark = await provider.mark(PortoMarkRequest(porto=porto))
    assert mark.wire == "internetmarke"
    assert mark.provider == "deutschepost"


@pytest.mark.offline
@pytest.mark.asyncio
async def test_pinned_internetmarke_wire(client) -> None:
    provider, _adapter = _install(client)
    porto = provider.resolve(country_code="DE", weight=20)
    mark = await provider.mark(
        PortoMarkRequest(porto=porto),
        ExecutionParameters(wire="internetmarke"),
    )
    assert mark.wire == "internetmarke"


@pytest.mark.offline
@pytest.mark.asyncio
async def test_unknown_wire_pin_is_capability_unsupported(client) -> None:
    provider, _adapter = _install(client)
    porto = provider.resolve(country_code="DE", weight=20)
    with pytest.raises(PortoError) as exc:
        await provider.mark(
            PortoMarkRequest(porto=porto),
            ExecutionParameters(wire="no-such-wire"),
        )
    assert exc.value.code == PortoErrorCode.PORTO_CAPABILITY_UNSUPPORTED
