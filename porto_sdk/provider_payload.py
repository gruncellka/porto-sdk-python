"""Sanitize provider payloads before they land on public models.

provider_raw is opaque. Its shape is not part of Porto compatibility guarantees.
Secrets are dropped (not masked) before stash.
"""

from __future__ import annotations

from typing import Any

_SECRET_PARTS = (
    "password",
    "token",
    "secret",
    "authorization",
    "api_key",
    "apikey",
    "credential",
    "cookie",
    "bearer",
)


def _secret_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in _SECRET_PARTS)


def sanitize_provider_payload(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if _secret_key(name):
                continue
            cleaned[name] = sanitize_provider_payload(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize_provider_payload(item) for item in value]
    return value
