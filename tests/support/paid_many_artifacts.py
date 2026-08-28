"""Persist paid Internetmarke multi-position checkout investigation dumps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from porto_sdk.adapters.deutschepost.internetmarke.document_payload import (
    extract_png_entries,
    inspect_document_payload,
)


def paid_many_dir(slug: str, sdk: str = "python") -> Path:
    here = Path(__file__).resolve()
    lab_root = next(
        (
            parent
            for parent in here.parents
            if (parent / "labs" / "experiments" / "internetmarke").is_dir()
        ),
        Path.cwd(),
    )
    return (
        lab_root / "labs" / "experiments" / "internetmarke" / "artifacts" / "paid-many" / sdk / slug
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


async def persist_paid_many_artifacts(
    *,
    slug: str,
    marks: list[Any],
    trace: dict[str, Any] | None,
) -> dict[str, Any]:
    target = paid_many_dir(slug)
    target.mkdir(parents=True, exist_ok=True)
    png_dir = target / "pngs"
    png_dir.mkdir(parents=True, exist_ok=True)

    request = (trace or {}).get("request") or {}
    response = (trace or {}).get("response") or {}
    checkout = {
        "url": (trace or {}).get("url"),
        "positions_length": len(request.get("positions") or []),
        "total": request.get("total"),
        "productCodes": [
            position.get("productCode") for position in (request.get("positions") or [])
        ],
        "shopOrderId": response.get("shopOrderId") or request.get("shopOrderId"),
        "request": _jsonable(request),
        "response": _jsonable(response),
        "response_headers": _jsonable((trace or {}).get("response_headers") or {}),
    }
    (target / "checkout.json").write_text(json.dumps(checkout, indent=2, default=str) + "\n")

    link = getattr(marks[0], "content", None) if marks else None
    inspect: dict[str, Any] = {
        "link": link,
        "mark_count": len(marks),
        "external_ids": [getattr(mark, "external_id", None) for mark in marks],
        "png_count": 0,
        "correlation_observed": None,
    }
    download_headers: dict[str, str] = {}
    if isinstance(link, str) and link.startswith("http"):
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(link)
        payload = resp.content
        download_headers = {str(key): str(value) for key, value in resp.headers.items()}
        (target / "document.bin").write_bytes(payload)
        inspect.update(inspect_document_payload(payload))
        inspect["download_headers"] = download_headers
        extracted = extract_png_entries(payload)
        inspect["png_count"] = len(extracted)
        for name, body in extracted:
            safe = Path(name).name or "entry.png"
            (png_dir / safe).write_bytes(body)
        if inspect.get("kind") == "zip" and inspect["png_count"] == 3:
            inspect["correlation_observed"] = (
                "three PNG members; ZIP namelist order is recorded, not treated as position order"
            )
        elif inspect.get("kind") == "png" and inspect["png_count"] == 1:
            inspect["correlation_observed"] = "single inline PNG for three positions"
        else:
            inspect["correlation_observed"] = "no stable position mapping assumed"
    (target / "inspect.json").write_text(json.dumps(inspect, indent=2, default=str) + "\n")
    return inspect
