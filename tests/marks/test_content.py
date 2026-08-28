"""Core mark document fetch: PDF/PNG magic, optional adapter normalize, URL checks."""

from __future__ import annotations

import pytest

from porto_sdk.errors import ValidationError
from porto_sdk.execution import PortoMark, build_porto_mark
from porto_sdk.mark_content import fetch_mark_bytes, normalize_mark_document
from porto_sdk.transport.http_client import HttpClient


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _sample_mark(**overrides) -> PortoMark:
    mark = build_porto_mark(
        provider="example",
        wire="internetmarke",
        content="https://example.test/stamp.png",
        content_type="image/png",
        amount=95,
        generated_at="2026-07-07T12:00:00",
    )
    if not overrides:
        return mark
    return mark.model_copy(update=overrides)


def test_normalize_mark_document_pdf_passthrough() -> None:
    pdf = b"%PDF-1.4\n"
    mark = _sample_mark(content_type="application/pdf")
    assert normalize_mark_document(mark, pdf) == pdf


def test_normalize_mark_document_png_passthrough() -> None:
    png = _png_bytes()
    assert normalize_mark_document(_sample_mark(), png) == png


def test_normalize_mark_document_rejects_unknown_payload() -> None:
    with pytest.raises(ValidationError):
        normalize_mark_document(_sample_mark(), b"not-a-stamp")


def test_normalize_mark_document_uses_normalize_callback() -> None:
    png = _png_bytes()

    def fake(payload: bytes) -> bytes:
        if payload.startswith(b"FAKE"):
            return payload[4:]
        raise ValueError("unsupported")

    assert normalize_mark_document(_sample_mark(), b"FAKE" + png, normalize=fake) == png


@pytest.mark.offline
@pytest.mark.asyncio
async def test_fetch_mark_bytes_downloads_png(monkeypatch: pytest.MonkeyPatch) -> None:
    png = _png_bytes()

    class _Response:
        status_code = 200

        def __init__(self) -> None:
            self.content = png

    async def fake_request(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _Response()

    client = HttpClient(retries=1)
    monkeypatch.setattr(client._client, "request", fake_request)
    result = await fetch_mark_bytes(_sample_mark(), http_client=client, retries=1)
    assert result == png
    await client.close()


@pytest.mark.offline
@pytest.mark.asyncio
async def test_fetch_mark_bytes_rejects_non_url_content() -> None:
    mark = _sample_mark(content="inline:not-a-url")
    with pytest.raises(ValidationError, match="not a downloadable URL"):
        await fetch_mark_bytes(mark, retries=1)
