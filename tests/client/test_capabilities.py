"""Execution capabilities and billing service tests."""

import pytest

from porto_sdk import PortoClient, PortoConfig
from porto_sdk.adapters.execution_registry import supports_billing, supports_execution
from porto_sdk.adapters.unavailable_execution import UnavailableExecutionAdapter
from porto_sdk.config import ProviderRuntimeConfig
from porto_sdk.errors import PortoError, PortoErrorCode
from tests.support.bound_provider import bound_provider


@pytest.mark.offline
def test_supports_methods_from_porto_data_manifest() -> None:
    assert supports_billing("deutschepost", "wallet")
    assert supports_execution("deutschepost", "mark")

@pytest.mark.offline
def test_swisspost_has_no_internetmarke_execution_methods() -> None:
    assert not supports_billing("swisspost", "wallet")
    assert not supports_execution("swisspost", "mark")


@pytest.mark.offline
@pytest.mark.asyncio
async def test_billing_raises_capability_unsupported_without_wallet() -> None:
    client = PortoClient(PortoConfig(providers={"swisspost": ProviderRuntimeConfig()}))
    with pytest.raises(PortoError) as exc:
        await bound_provider(client, "swisspost").wallet.balance()
    assert exc.value.code == PortoErrorCode.PORTO_CAPABILITY_UNSUPPORTED
    assert exc.value.details["capability"] == "wallet"


@pytest.mark.offline
@pytest.mark.asyncio
async def test_unavailable_execution_adapter_fails_clearly() -> None:
    adapter = UnavailableExecutionAdapter("swisspost", "none")
    with pytest.raises(PortoError) as exc:
        await adapter.balance()
    assert exc.value.code == PortoErrorCode.PORTO_CAPABILITY_UNSUPPORTED
    assert exc.value.details["capability"] == "wallet"
    assert exc.value.provider == "swisspost"
