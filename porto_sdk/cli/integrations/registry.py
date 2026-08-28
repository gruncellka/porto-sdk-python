"""CLI wire registry: compose provider modules; generic fallback only."""

from __future__ import annotations

from typing import Any, Protocol

from .deutschepost import DeutschepostInternetmarke
from .swisspost import SwisspostWebstamp


class WireDefinition(Protocol):
    def map_payload(self, opts: Any) -> dict[str, Any]: ...
    def build_status_summary(self, wire_config: dict[str, Any] | None) -> dict[str, Any]: ...
    def build_login_summary(self, opts: Any, config_path: str) -> dict[str, Any]: ...


def _get_opt(opts: Any, key: str, default: Any = None) -> Any:
    return getattr(opts, key, default)


class _GenericWire:
    def map_payload(self, opts: Any) -> dict[str, Any]:
        creds: dict[str, str] = {}
        for k in (
            "username",
            "password",
            "client_id",
            "client_secret",
            "api_key",
            "api_secret",
            "partner_id",
            "customer_id",
            "application_id",
        ):
            v = _get_opt(opts, k)
            if v is not None and isinstance(v, str):
                creds[k] = v
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
            "credential_keys": [k for k in creds if k != "password"],
        }

    def build_login_summary(self, opts: Any, config_path: str) -> dict[str, Any]:
        return {"saved": config_path, "credentials_saved": True}


CLI_WIRE_DEFINITIONS: dict[str, dict[str, WireDefinition]] = {
    "deutschepost": {"internetmarke": DeutschepostInternetmarke()},
    "swisspost": {"webstamp": SwisspostWebstamp()},
}

_GENERIC = _GenericWire()


def get_default_wire(provider: str) -> str:
    p = provider.strip().lower()
    if p in CLI_WIRE_DEFINITIONS:
        defs = CLI_WIRE_DEFINITIONS[p]
        return next(iter(defs.keys()), "default")
    return "default"


def get_definition(provider: str, wire: str) -> WireDefinition:
    p = provider.strip().lower()
    w = wire.strip().lower()
    defs = CLI_WIRE_DEFINITIONS.get(p, {})
    return defs.get(w) or _GENERIC


def build_wire_payload(opts: Any, provider: str, wire: str) -> dict[str, Any]:
    return get_definition(provider, wire).map_payload(opts)


def get_wire_status_summary(
    wire_config: dict[str, Any] | None, provider: str, wire: str
) -> dict[str, Any]:
    summary = get_definition(provider, wire).build_status_summary(wire_config)
    return {"provider": provider, "wire": wire, **summary}


def build_login_output_summary(
    opts: Any, provider: str, wire: str, config_path: str
) -> dict[str, Any]:
    summary = get_definition(provider, wire).build_login_summary(opts, config_path)
    return {"provider": provider, "wire": wire, **summary}
