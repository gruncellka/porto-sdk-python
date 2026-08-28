"""Normalize Internetmarke document downloads (DHL often returns a ZIP containing 0.png)."""

from __future__ import annotations

import io
import zipfile
from typing import Any


def inspect_document_payload(data: bytes) -> dict[str, Any]:
    """Describe PNG or ZIP payload without assuming entry order equals cart position."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return {
            "kind": "png",
            "size": len(data),
            "entries": [{"name": "inline.png", "size": len(data), "png": True}],
            "png_names_zip_order": ["inline.png"],
            "png_names_sorted": ["inline.png"],
        }
    if data.startswith(b"PK"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            zip_order = list(archive.namelist())
            entries = []
            png_zip_order: list[str] = []
            for name in zip_order:
                info = archive.getinfo(name)
                is_png = name.lower().endswith(".png")
                if is_png:
                    png_zip_order.append(name)
                entries.append(
                    {
                        "name": name,
                        "size": info.file_size,
                        "compress_size": info.compress_size,
                        "compress_type": info.compress_type,
                        "png": is_png,
                    }
                )
            return {
                "kind": "zip",
                "size": len(data),
                "namelist": zip_order,
                "entries": entries,
                "png_names_zip_order": png_zip_order,
                "png_names_sorted": sorted(png_zip_order, key=str.lower),
            }
    return {
        "kind": "unknown",
        "size": len(data),
        "magic": data[:8].hex(),
        "entries": [],
        "png_names_zip_order": [],
        "png_names_sorted": [],
    }


def extract_png_entries(data: bytes) -> list[tuple[str, bytes]]:
    """Return PNG members in ZIP archive order. A lone PNG is one inline entry."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return [("inline.png", data)]
    if not data.startswith(b"PK"):
        return []
    out: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if name.lower().endswith(".png"):
                out.append((name, archive.read(name)))
    return out


def normalize_document_payload(data: bytes) -> bytes:
    """Return raw PNG bytes from an Internetmarke document payload (PNG or ZIP wrapper)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data
    if data.startswith(b"PK"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            png_names = sorted(name for name in archive.namelist() if name.lower().endswith(".png"))
            if not png_names:
                raise ValueError("Internetmarke stamp ZIP contains no PNG entry")
            return archive.read(png_names[0])
    raise ValueError(
        f"Unsupported Internetmarke stamp payload (magic={data[:4]!r}, len={len(data)})"
    )
