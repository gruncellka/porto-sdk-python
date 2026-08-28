"""Internetmarke document ZIP/PNG unwrap stays adapter-local."""

from __future__ import annotations

import io
import zipfile

from porto_sdk.adapters.deutschepost.internetmarke.document_payload import (
    extract_png_entries,
    inspect_document_payload,
    normalize_document_payload,
)


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _zip_png(png: bytes, name: str = "0.png") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(name, png)
    return buf.getvalue()


def test_normalize_document_payload_png_passthrough() -> None:
    png = _png_bytes()
    assert normalize_document_payload(png) == png


def test_normalize_document_payload_zip_to_png() -> None:
    png = _png_bytes()
    assert normalize_document_payload(_zip_png(png)) == png


def test_internetmarke_normalize_unwraps_zip() -> None:
    png = _png_bytes()
    assert normalize_document_payload(_zip_png(png)) == png


def test_inspect_zip_lists_pngs_without_position_mapping() -> None:
    png = _png_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("2.png", png)
        archive.writestr("0.png", png)
        archive.writestr("1.png", png)
    payload = buf.getvalue()
    inspect = inspect_document_payload(payload)
    assert inspect["kind"] == "zip"
    assert inspect["png_names_zip_order"] == ["2.png", "0.png", "1.png"]
    assert inspect["png_names_sorted"] == ["0.png", "1.png", "2.png"]
    extracted = extract_png_entries(payload)
    assert [name for name, _ in extracted] == ["2.png", "0.png", "1.png"]
