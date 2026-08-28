"""
CLI config store. Single responsibility: read/write ~/.porto/config.json.
Provider-scoped structure: providers.<provider>.wires.<wire>.
Merge order: explicit > file > env > SDK default.
Defaults live here only; never in commands, helpers, or adapters.
CLI uses getProviderWire / getConfigCheckSummary; never reads cfg.wires directly.
"""

from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

from ..config import PortoConfig, ProviderRuntimeConfig, WireConfig

DEFAULT_PROVIDER = "deutschepost"

CONFIG_DIR = Path.home() / ".porto"
CONFIG_PATH = CONFIG_DIR / "config.json"


def _read_file_config() -> dict[str, Any]:
    """Read config file. Returns empty dict if missing or invalid."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError):
        return {}


def _to_canonical(raw: dict[str, Any]) -> dict[str, Any]:
    """Canonical config shape: default_provider + providers.<provider>.wires."""
    return {
        "default_provider": raw.get("default_provider", DEFAULT_PROVIDER),
        "providers": raw.get("providers") or {},
    }


def _resolve_provider(
    file_config: dict[str, Any],
    env_provider: str | None,
    explicit_override: str | None,
) -> str:
    """Provider resolution: explicit > file > env > default."""
    if explicit_override and str(explicit_override).strip():
        return str(explicit_override).strip().lower()
    if file_config.get("default_provider"):
        return str(file_config["default_provider"]).strip().lower()
    if env_provider and str(env_provider).strip():
        return str(env_provider).strip().lower()
    return DEFAULT_PROVIDER


def _flatten_wires_for_provider(
    file_config: dict[str, Any], provider_id: str
) -> dict[str, WireConfig]:
    """Build wires dict from file for given provider."""
    provider_id = provider_id.strip().lower()
    providers = file_config.get("providers") or {}
    prov = providers.get(provider_id, {})
    if not isinstance(prov, dict):
        return {}
    wires_raw = prov.get("wires") or {}
    if not isinstance(wires_raw, dict):
        return {}
    result: dict[str, WireConfig] = {}
    for wire_id, wire_val in wires_raw.items():
        if not isinstance(wire_val, dict):
            continue
        base_url = wire_val.get("base_url") or wire_val.get("baseUrl")
        creds_raw = wire_val.get("credentials") or {}
        creds = {k: str(v) for k, v in creds_raw.items() if isinstance(v, str)}
        result[wire_id] = WireConfig(
            base_url=base_url.rstrip("/") if base_url else None,
            credentials=creds if creds else None,
        )
    return result


def load_porto_config(
    provider_override: str | None = None,
    env: dict[str, str] | None = None,
) -> PortoConfig:
    """Load merged PortoConfig for CLI use. Single entry point for config resolution."""
    file_raw = _read_file_config()
    file_config = _to_canonical(file_raw)

    env_config = PortoConfig.from_env(env)
    env_provider = (env or os.environ).get("PORTO_PROVIDER")

    provider_id = _resolve_provider(file_config, env_provider, provider_override)
    wires = _flatten_wires_for_provider(file_config, provider_id)

    return PortoConfig(
        data=env_config.data,
        cache=env_config.cache,
        transport=env_config.transport,
        providers={provider_id: ProviderRuntimeConfig(wires=wires if wires else None)},
    )


def get_provider_wire(provider_id: str, wire_id: str) -> dict[str, Any] | None:
    """Get wire config for provider. CLI must use this API; never cfg.wires.*."""
    file_raw = _read_file_config()
    file_config = _to_canonical(file_raw)
    provider_id = provider_id.strip().lower()
    wire_id = wire_id.strip().lower()
    prov = (file_config.get("providers") or {}).get(provider_id, {})
    if not isinstance(prov, dict):
        return None
    wire_cfg = (prov.get("wires") or {}).get(wire_id)
    if not isinstance(wire_cfg, dict):
        return None
    base_url = wire_cfg.get("base_url") or wire_cfg.get("baseUrl")
    creds = wire_cfg.get("credentials")
    if isinstance(creds, dict):
        creds = {k: v for k, v in creds.items() if isinstance(v, str)}
    return {"base_url": base_url, "credentials": creds or {}}


def list_provider_wire_ids(provider_id: str) -> list[str]:
    """List wire ids for provider. CLI uses this instead of cfg.wires."""
    file_raw = _read_file_config()
    file_config = _to_canonical(file_raw)
    provider_id = provider_id.strip().lower()
    prov = (file_config.get("providers") or {}).get(provider_id, {})
    if not isinstance(prov, dict):
        return []
    wires = prov.get("wires") or {}
    return list(wires.keys()) if isinstance(wires, dict) else []


def save_provider_wire(
    provider_id: str,
    wire_id: str,
    payload: dict[str, Any],
) -> None:
    """Save wire config for provider. Generic API."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    raw = _read_file_config()
    config = _to_canonical(raw)
    config.setdefault("providers", {})
    provider_id = provider_id.strip().lower()
    wire_id = wire_id.strip().lower()
    if provider_id not in config["providers"]:
        config["providers"][provider_id] = {"wires": {}}
    prov = config["providers"][provider_id]
    prov.setdefault("wires", {})
    base_url = payload.get("base_url")
    creds = payload.get("credentials")
    if isinstance(creds, dict):
        creds = {k: str(v) for k, v in creds.items() if v is not None}
    prov["wires"][wire_id] = {
        "base_url": base_url.rstrip("/") if base_url else None,
        "credentials": creds or {},
    }
    config["default_provider"] = config.get("default_provider", DEFAULT_PROVIDER)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def clear_provider_wire(provider_id: str, wire_id: str) -> bool:
    """Clear wire config for provider."""
    if not CONFIG_PATH.exists():
        return False
    raw = _read_file_config()
    config = _to_canonical(raw)
    prov = (config.get("providers") or {}).get(provider_id.strip().lower(), {})
    if not isinstance(prov, dict):
        return False
    wires = prov.get("wires") or {}
    if wire_id not in wires:
        return False
    del prov["wires"][wire_id]
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def get_config_path() -> Path:
    """Config file path for display."""
    return CONFIG_PATH


def config_exists() -> bool:
    """Whether config file exists."""
    return CONFIG_PATH.exists()


def get_config_check_summary(
    provider_override: str | None = None,
) -> dict[str, Any]:
    """Config check summary. CLI uses this API; never reads config directly."""
    config = load_porto_config(provider_override=provider_override)
    provider = next(iter(sorted(config.configured_provider_ids())), DEFAULT_PROVIDER)
    wire_ids = list_provider_wire_ids(provider)
    has_auth = False
    for wire_id in wire_ids:
        cfg = get_provider_wire(provider, wire_id)
        if cfg and cfg.get("credentials") and len(cfg["credentials"]) > 0:
            has_auth = True
            break
    timeout = config.resolved_transport().timeout
    timeout_seconds = (
        int(timeout.total_seconds()) if isinstance(timeout, timedelta) else int(timeout)
    )
    return {
        "provider": provider,
        "data": config.data,
        "timeout": timeout_seconds,
        "retries": config.resolved_transport().retries,
        "has_auth": has_auth,
        "wires": wire_ids,
    }


def init_config(force: bool = False) -> dict[str, Any]:
    """Create config file with minimal structure. No credentials."""
    if CONFIG_PATH.exists() and not force:
        return {"created": False, "path": str(CONFIG_PATH)}
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    minimal = {"default_provider": DEFAULT_PROVIDER, "providers": {}}
    CONFIG_PATH.write_text(json.dumps(minimal, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"created": True, "path": str(CONFIG_PATH)}


def get_config_summary(provider_override: str | None = None) -> dict[str, Any]:
    """Config summary for CLI config check. Use get_config_check_summary for full."""
    s = get_config_check_summary(provider_override)
    return {
        "provider": s["provider"],
        "data": s["data"],
        "data_path": s["data"],
        "timeout": s["timeout"],
        "retries": s["retries"],
        "has_auth": s["has_auth"],
    }
