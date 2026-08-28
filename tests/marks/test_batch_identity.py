"""Unpaid mark(many) core dispatch: empty list, sequential loop, mixed lists without mark_many."""

from __future__ import annotations

import pytest

from porto_sdk.errors import PortoError, PortoErrorCode
from porto_sdk.execution import PortoMarkRequest, build_porto_mark
from porto_sdk.services.porto_execution import PortoExecution
from porto_sdk.services.porto_resolver import Porto
from tests.support.addresses import licko_recipient, licko_sender
from tests.support.bound_provider import bound_provider

DE_SENDER = licko_sender()
DE_RECIPIENT = licko_recipient("DE")


class _CaptureAdapter:
    def __init__(self) -> None:
        self.requests: list = []

    @property
    def provider_id(self) -> str:
        return "deutschepost"

    @property
    def wire_id(self) -> str:
        return "internetmarke"

    async def mark(self, request, resolved_product=None, execution=None):
        self.requests.append(request)
        return build_porto_mark(
            provider="deutschepost",
            wire="internetmarke",
            content=f"https://example.test/mark-{len(self.requests)}.png",
            content_type="image/png",
            amount=request.value,
            external_id=request.idempotency_key,
        )


def _execution(client) -> tuple[PortoExecution, _CaptureAdapter]:
    bound = bound_provider(client)
    adapter = _CaptureAdapter()
    execution = bound._execution
    execution.adapter = adapter
    return execution, adapter


def _resolve(client) -> Porto:
    return bound_provider(client).resolve(country_code="DE", weight=20)


def _other(client) -> Porto:
    return bound_provider(client).resolve(country_code="DE", weight=400)


def _requests(*portos: Porto, **kwargs) -> list[PortoMarkRequest]:
    return [PortoMarkRequest(porto=item, **kwargs) for item in portos]


async def _expect_code(execution, items, code: PortoErrorCode) -> PortoError:
    with pytest.raises(PortoError) as exc:
        await execution.mark(items)
    assert exc.value.code == code
    return exc.value


@pytest.mark.offline
@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1, 2, 3])
async def test_homogeneous_equal_items(client, count: int) -> None:
    porto = _resolve(client)
    execution, adapter = _execution(client)
    marks = await execution.mark(_requests(*([porto] * count)))
    assert len(marks) == count
    assert len(adapter.requests) == count
    assert len({mark.id for mark in marks}) == count
    assert {mark.wire for mark in marks} == {"internetmarke"}


@pytest.mark.offline
@pytest.mark.asyncio
async def test_empty_collection_invalid(client) -> None:
    execution, adapter = _execution(client)
    await _expect_code(execution, [], PortoErrorCode.PORTO_MARK_INVALID)
    assert adapter.requests == []


@pytest.mark.offline
@pytest.mark.asyncio
async def test_core_dispatches_mixed_in_order_when_adapter_has_no_mark_many(client) -> None:
    porto = _resolve(client)
    other = _other(client)
    execution, adapter = _execution(client)
    marks = await execution.mark(_requests(porto, other, porto))
    assert len(marks) == 3
    assert [row.value for row in adapter.requests] == [porto.amount, other.amount, porto.amount]


@pytest.mark.offline
@pytest.mark.asyncio
async def test_per_item_fields_do_not_block_many(client) -> None:
    porto = _resolve(client)
    execution, adapter = _execution(client)
    marks = await execution.mark(
        [
            PortoMarkRequest(porto=porto, idempotency="one", mime="image/png", sender=DE_SENDER),
            PortoMarkRequest(
                porto=porto,
                idempotency="two",
                mime="application/pdf",
                recipient=DE_RECIPIENT,
            ),
            PortoMarkRequest(porto=porto, idempotency="three"),
        ]
    )
    assert len(marks) == 3
    assert [row.idempotency_key for row in adapter.requests] == ["one", "two", "three"]


@pytest.mark.offline
@pytest.mark.asyncio
async def test_cardinality_positional_correspondence(client) -> None:
    porto = _resolve(client)
    execution, adapter = _execution(client)
    marks = await execution.mark(
        [
            PortoMarkRequest(porto=porto, idempotency="pos-0"),
            PortoMarkRequest(porto=porto, idempotency="pos-1"),
            PortoMarkRequest(porto=porto, idempotency="pos-2"),
        ]
    )
    assert [mark.external_id for mark in marks] == ["pos-0", "pos-1", "pos-2"]
    assert len({mark.id for mark in marks}) == 3
    assert {mark.wire for mark in marks} == {"internetmarke"}
    assert len(adapter.requests) == 3
