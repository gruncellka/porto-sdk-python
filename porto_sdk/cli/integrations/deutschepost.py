"""Deutsche Post CLI wire definitions."""

from __future__ import annotations

from typing import Any


def _mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


def _get_opt(opts: Any, key: str, default: Any = None) -> Any:
    return getattr(opts, key, default)


class DeutschepostInternetmarke:
    def map_payload(self, opts: Any) -> dict[str, Any]:
        creds: dict[str, str] = {
            "username": str(_get_opt(opts, "username", "") or ""),
            "password": str(_get_opt(opts, "password", "") or ""),
        }
        if _get_opt(opts, "dhl_api_key"):
            creds["dhl_api_key"] = str(_get_opt(opts, "dhl_api_key"))
        if _get_opt(opts, "dhl_api_secret"):
            creds["dhl_api_secret"] = str(_get_opt(opts, "dhl_api_secret"))
        if _get_opt(opts, "partner_id"):
            creds["partner_id"] = str(_get_opt(opts, "partner_id"))
        base_url = _get_opt(opts, "base_url")
        return {
            "base_url": base_url.rstrip("/") if base_url else None,
            "credentials": creds,
        }

    def build_status_summary(self, wire_config: dict[str, Any] | None) -> dict[str, Any]:
        creds = (wire_config or {}).get("credentials") or {}
        return {
            "authenticated": bool(creds and len(creds) > 0),
            "username": creds.get("username"),
            "base_url": (wire_config or {}).get("base_url"),
            "has_dhl_api_key": bool(creds.get("dhl_api_key")),
            "has_dhl_api_secret": bool(creds.get("dhl_api_secret")),
        }

    def build_login_summary(self, opts: Any, config_path: str) -> dict[str, Any]:
        return {
            "saved": config_path,
            "username": _get_opt(opts, "username"),
            "password": _mask_secret(_get_opt(opts, "password")),
            "dhl_api_key": _mask_secret(_get_opt(opts, "dhl_api_key")),
            "dhl_api_secret": _mask_secret(_get_opt(opts, "dhl_api_secret")),
            "partner_id": _get_opt(opts, "partner_id"),
        }
