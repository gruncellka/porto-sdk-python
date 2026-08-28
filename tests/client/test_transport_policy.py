from pathlib import Path

import httpx
import pytest

from porto_sdk import PortoClient, PortoConfig
from porto_sdk.transport.http_client import HttpClient


class _Response:
    def __init__(self, status_code: int):
        self.status_code = status_code


@pytest.mark.offline
@pytest.mark.asyncio
async def test_retries_on_5xx_for_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    client = HttpClient(retries=3)
    calls = {"count": 0}

    async def fake_request(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        return _Response(500 if calls["count"] < 3 else 200)

    async def fake_sleep(*args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(client._client, "request", fake_request)
    monkeypatch.setattr("porto_sdk.transport.http_client.asyncio.sleep", fake_sleep)

    response = await client.request(method="GET", url="https://example.test", idempotent=True)
    assert response.status_code == 200
    assert calls["count"] == 3


@pytest.mark.offline
@pytest.mark.asyncio
async def test_non_idempotent_without_key_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    client = HttpClient(retries=3)
    calls = {"count": 0}

    async def fake_request(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(client._client, "request", fake_request)

    with pytest.raises(Exception):
        await client.request(method="POST", url="https://example.test", idempotent=False)
    assert calls["count"] == 1


@pytest.mark.offline
@pytest.mark.asyncio
async def test_non_idempotent_with_key_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    client = HttpClient(retries=3)
    calls = {"count": 0}

    async def fake_request(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        if calls["count"] < 2:
            raise httpx.ConnectError("boom")
        return _Response(200)

    async def fake_sleep(*args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(client._client, "request", fake_request)
    monkeypatch.setattr("porto_sdk.transport.http_client.asyncio.sleep", fake_sleep)

    response = await client.request(
        method="POST",
        url="https://example.test",
        idempotent=False,
        idempotency_key="abc",
    )
    assert response.status_code == 200
    assert calls["count"] == 2


class _FakeTransport:
    async def request(self, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("injected transport should not send during client init")

    async def close(self) -> None:
        return None


@pytest.mark.offline
def test_injected_transport_is_shared(porto_data_path: Path) -> None:
    fake = _FakeTransport()
    client = PortoClient(PortoConfig(data=porto_data_path), transport=fake)
    assert client._http_client is fake


@pytest.mark.offline
def test_default_transport_is_http_client(porto_data_path: Path) -> None:
    client = PortoClient(PortoConfig(data=porto_data_path))
    assert isinstance(client._http_client, HttpClient)
