"""Wallet balance adapter tests."""

import pytest

from porto_sdk.adapters.deutschepost.internetmarke.adapter import InternetmarkeAdapter
from porto_sdk.errors import PortoError, PortoErrorCode


class _FakeAuth:
    def __init__(self, balance_cents: int | None) -> None:
        self._balance = balance_cents

    async def authenticate(self) -> None:
        return None

    def get_wallet_balance_cents(self) -> int | None:
        return self._balance


@pytest.mark.offline
@pytest.mark.asyncio
async def test_get_wallet_balance_returns_prepaid_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = InternetmarkeAdapter(
        username="u",
        password="p",
        api_key="k",
        api_secret="s",
        base_url="https://example.test",
    )
    monkeypatch.setattr(adapter, "_auth_for", lambda execution=None: _FakeAuth(125))

    wallet = await adapter.balance()

    assert wallet.balance_cents == 125
    assert wallet.currency == "EUR"
    assert wallet.provider == "deutschepost"
    assert wallet.wire == "internetmarke"
    assert wallet.billing_model == "prepaid"


@pytest.mark.offline
@pytest.mark.asyncio
async def test_get_wallet_balance_missing_from_provider_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = InternetmarkeAdapter(
        username="u",
        password="p",
        api_key="k",
        api_secret="s",
        base_url="https://example.test",
    )
    monkeypatch.setattr(adapter, "_auth_for", lambda execution=None: _FakeAuth(None))

    with pytest.raises(PortoError) as exc:
        await adapter.balance()
    assert exc.value.code == PortoErrorCode.PORTO_MARK_FAILED
