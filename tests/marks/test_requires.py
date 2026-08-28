"""Mark requires gates — catalog tokens, not presentation/layout."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from porto_sdk.errors import PortoError, PortoErrorCode
from porto_sdk.execution import PortoMarkRequest, build_porto_mark
from porto_sdk.requires import ADDRESS, RECIPIENT, SENDER
from porto_sdk.services.porto_execution import PortoExecution
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
            content="https://example.test/mark.png",
            content_type="image/png",
            amount=request.value,
        )


def _execution(client) -> tuple[PortoExecution, _CaptureAdapter]:
    bound = bound_provider(client)
    adapter = _CaptureAdapter()
    execution = bound._execution
    execution.adapter = adapter
    return execution, adapter


def _resolve(client, *, service_ids: list[str] | None = None, services: list[str] | None = None):
    return bound_provider(client).resolve(
        country_code="DE",
        weight=20,
        services=services,
        service_ids=service_ids,
    )


@pytest.mark.offline
def test_deutschepost_stamp_has_empty_requires(client) -> None:
    porto = _resolve(client)
    assert porto.mark_type == "stamp"
    assert porto.requires == ()


@pytest.mark.offline
@pytest.mark.asyncio
async def test_stamp_strips_extra_addresses_and_allows_many(client) -> None:
    porto = _resolve(client)
    execution, adapter = _execution(client)
    prepared = await execution.prepare(
        PortoMarkRequest(
            porto=porto,
            sender=DE_SENDER,
            recipient=DE_RECIPIENT,
        )
    )
    assert prepared.request.origin is None
    assert prepared.request.destination is None

    marks = await execution.mark(
        [
            PortoMarkRequest(porto=porto),
            PortoMarkRequest(porto=porto),
        ]
    )
    assert len(marks) == 2
    assert len(adapter.requests) == 2


@pytest.mark.offline
@pytest.mark.asyncio
async def test_address_bearing_many_succeeds_through_core_prepare(client) -> None:
    porto = _resolve(client).model_copy(update={"requires": tuple(sorted(ADDRESS))})
    execution, adapter = _execution(client)
    marks = await execution.mark(
        [
            PortoMarkRequest(porto=porto, sender=DE_SENDER, recipient=DE_RECIPIENT),
            PortoMarkRequest(porto=porto, sender=DE_SENDER, recipient=DE_RECIPIENT),
        ]
    )
    assert len(marks) == 2
    assert len(adapter.requests) == 2


@pytest.mark.offline
@pytest.mark.asyncio
async def test_mixed_portos_succeed_through_core_prepare_in_order(client) -> None:
    small = _resolve(client)
    large = bound_provider(client).resolve(country_code="DE", weight=400)
    execution, adapter = _execution(client)
    marks = await execution.mark([PortoMarkRequest(porto=small), PortoMarkRequest(porto=large)])
    assert len(marks) == 2
    assert [row.value for row in adapter.requests] == [small.amount, large.amount]


@pytest.mark.offline
@pytest.mark.asyncio
async def test_missing_sender_when_required(client) -> None:
    porto = _resolve(client).model_copy(update={"requires": (SENDER, RECIPIENT)})
    execution, _adapter = _execution(client)
    with pytest.raises(PortoError) as exc:
        await execution.mark(PortoMarkRequest(porto=porto, recipient=DE_RECIPIENT))
    assert exc.value.code == PortoErrorCode.PORTO_ADDRESS_SENDER_REQUIRED


@pytest.mark.offline
@pytest.mark.asyncio
async def test_mark_does_not_re_resolve(client) -> None:
    porto = _resolve(client)
    execution, _adapter = _execution(client)
    boom = MagicMock()
    boom.resolve.side_effect = AssertionError("mark must not re-resolve")
    boom.get_service_price.return_value = None
    execution.set_resolver(boom)
    await execution.mark(PortoMarkRequest(porto=porto))
    boom.resolve.assert_not_called()


@pytest.mark.offline
@pytest.mark.asyncio
async def test_registered_stamp_does_not_require_address(client) -> None:
    porto = _resolve(client, services=["registered"], service_ids=["einschreiben"])
    assert not ADDRESS.intersection(porto.requires)
    execution, adapter = _execution(client)
    await execution.mark(PortoMarkRequest(porto=porto))
    assert adapter.requests[0].origin is None
    assert adapter.requests[0].destination is None
