"""Swiss Post CLI wire definitions."""

from __future__ import annotations

from typing import Any


def _get_opt(opts: Any, key: str, default: Any = None) -> Any:
    return getattr(opts, key, default)


class SwisspostWebstamp:
    def map_payload(self, opts: Any) -> dict[str, Any]:
        creds: dict[str, str] = {}
        if _get_opt(opts, "username"):
            creds["username"] = str(_get_opt(opts, "username"))
        if _get_opt(opts, "password"):
            creds["password"] = str(_get_opt(opts, "password"))
        if _get_opt(opts, "customer_id"):
            creds["customer_id"] = str(_get_opt(opts, "customer_id"))
        if _get_opt(opts, "application_id"):
            creds["application_id"] = str(_get_opt(opts, "application_id"))
        base_url = _get_opt(opts, "base_url")
        return {
            "base_url": base_url.rstrip("/") if base_url else None,
            "credentials": creds if creds else None,
        }

    def build_status_summary(self, wire_config: dict[str, Any] | None) -> dict[str, Any]:
        creds = (wire_config or {}).get("credentials") or {}
        return {
            "authenticated": bool(creds and len(creds) > 0),
            "base_url": (wire_config or {}).get("base_url"),
            "has_customer_id": bool(creds.get("customer_id")),
            "has_application_id": bool(creds.get("application_id")),
        }

    def build_login_summary(self, opts: Any, config_path: str) -> dict[str, Any]:
        return {"saved": config_path, "credentials_saved": True}
