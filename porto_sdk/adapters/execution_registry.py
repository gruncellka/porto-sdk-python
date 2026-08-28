"""
Execution registry — maps operator to execution adapter (internetmarke only today).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from ..config import PortoConfig, WireConfig
from .deutschepost.internetmarke.bootstrap import build_internetmarke_adapter
from .protocols.execution import ExecutionAdapter
from .unavailable_execution import UnavailableExecutionAdapter


def load_execution_manifest(
    provider_id: str,
    data_path: str | None = None,
) -> dict[str, Any]:
    """Load execution.json for an operator from porto-data."""
    provider = provider_id.strip().lower()
    candidates: list[Path] = []
    resolved_path = data_path
    if not resolved_path:
        try:
            from ..data.porto_data_registry import find_porto_data_path

            resolved_path = find_porto_data_path()
        except ValueError:
            resolved_path = None
    if resolved_path:
        for filename in ("execution.json",):
            candidates.append(Path(resolved_path) / "providers" / provider / filename)
            candidates.append(
                Path(resolved_path) / "porto_data" / "providers" / provider / filename
            )

    for path in candidates:
        if path.is_file():
            with path.open(encoding="utf-8") as handle:
                return json.load(handle)  # type: ignore[no-any-return]
    return {}


def _manifest_wire_view(
    manifest: dict[str, Any],
) -> tuple[str | None, dict[str, dict[str, list[str]]]]:
    """Normalize a per-provider execution.json manifest."""
    wire = manifest.get("wire")
    if wire:
        wire_id = str(wire).strip().lower()
        billing = [_normalize_capability(item) for item in (manifest.get("billing") or [])]
        execution = [_normalize_capability(item) for item in (manifest.get("execution") or [])]
        return wire_id, {wire_id: {"billing": billing, "execution": execution}}
    return None, {}


def _normalize_capability(item: Any) -> str:
    return str(item).strip().lower()


def list_applicable_wires(
    provider_id: str,
    operation: str,
    data_path: str | None = None,
) -> list[str]:
    """Wires in porto-data that can perform this operation for this provider."""
    cap_group, wanted = {
        "mark": ("execution", "mark"),
        "wallet": ("billing", "wallet"),
    }.get(operation, ("execution", operation))
    wanted = _normalize_capability(wanted)
    _, wires = _manifest_wire_view(load_execution_manifest(provider_id, data_path))
    found: list[str] = []
    for wire_id, entry in wires.items():
        methods = [_normalize_capability(item) for item in (entry.get(cap_group) or [])]
        if wanted in methods:
            found.append(wire_id)
    return found


def get_default_wire_id(provider_id: str, data_path: str | None = None) -> str | None:
    manifest = load_execution_manifest(provider_id, data_path)
    wire_id, _ = _manifest_wire_view(manifest)
    return wire_id


def list_wire_billing_methods(
    provider_id: str,
    wire_id: str,
    data_path: str | None = None,
) -> list[str]:
    manifest = load_execution_manifest(provider_id, data_path)
    _, wires = _manifest_wire_view(manifest)
    entry = wires.get(wire_id.strip().lower()) or {}
    return [str(item) for item in (entry.get("billing") or [])]


def list_wire_execution_methods(
    provider_id: str,
    wire_id: str,
    data_path: str | None = None,
) -> list[str]:
    manifest = load_execution_manifest(provider_id, data_path)
    _, wires = _manifest_wire_view(manifest)
    entry = wires.get(wire_id.strip().lower()) or {}
    return [str(item) for item in (entry.get("execution") or [])]


def supports_billing(
    provider_id: str,
    method: str,
    *,
    config: PortoConfig | None = None,
    wire_id: str | None = None,
    data_path: str | None = None,
    wires: dict[str, WireConfig] | None = None,
) -> bool:
    """True when porto-data manifest lists a billing method for the active wire."""
    provider = provider_id.strip().lower()
    normalized_method = _normalize_capability(method)
    data_path = data_path or (config.data if config else None)
    wire = wire_id
    if not wire:
        if wires is not None:
            wire = resolve_active_wire_for(provider, wires, data_path)
        elif config is not None:
            wire = _resolve_active_wire(config, data_path)
        else:
            wire = get_default_wire_id(provider, data_path)
    if not wire:
        return False
    methods = [item.lower() for item in list_wire_billing_methods(provider, wire, data_path)]
    return normalized_method in methods


def supports_execution(
    provider_id: str,
    method: str,
    *,
    config: PortoConfig | None = None,
    wire_id: str | None = None,
    data_path: str | None = None,
    wires: dict[str, WireConfig] | None = None,
) -> bool:
    """True when porto-data manifest lists an execution method for the active wire."""
    provider = provider_id.strip().lower()
    normalized_method = _normalize_capability(method)
    data_path = data_path or (config.data if config else None)
    wire = wire_id
    if not wire:
        if wires is not None:
            wire = resolve_active_wire_for(provider, wires, data_path)
        elif config is not None:
            wire = _resolve_active_wire(config, data_path)
        else:
            wire = get_default_wire_id(provider, data_path)
    if not wire:
        return False
    methods = [item.lower() for item in list_wire_execution_methods(provider, wire, data_path)]
    return normalized_method in methods


def _catalog_provider_wires(
    config: PortoConfig,
) -> tuple[str, dict[str, WireConfig] | None]:
    pid = config.normalize().default_provider
    return pid, config.wires_for(pid)


def resolve_active_wire(config: PortoConfig, data_path: str | None = None) -> str | None:
    provider, wires = _catalog_provider_wires(config)
    return resolve_active_wire_for(provider, wires, data_path)


def resolve_active_wire_for(
    provider_id: str,
    wires: dict[str, WireConfig] | None,
    data_path: str | None = None,
) -> str | None:
    provider = provider_id.strip().lower()
    if wires:
        default = get_default_wire_id(provider, data_path)
        if default and default in wires:
            return default
        return next(iter(wires.keys()), None)
    return get_default_wire_id(provider, data_path)


def _resolve_active_wire(config: PortoConfig, data_path: str | None) -> str | None:
    return resolve_active_wire(config, data_path)


def get_execution_adapter(
    provider_id: str,
    wires: dict[str, WireConfig] | None,
    env: dict[str, str] | None = None,
    data_path: str | None = None,
    *,
    http_client=None,
) -> ExecutionAdapter:
    """Resolve execution adapter from porto-data execution manifest + credentials."""
    provider = provider_id.strip().lower()
    wire_id = get_default_wire_id(provider, data_path)
    if not wire_id:
        return UnavailableExecutionAdapter(provider, "none")

    if wire_id == "internetmarke":
        return cast(
            ExecutionAdapter,
            build_internetmarke_adapter(wires, env, provider=provider, http_client=http_client),
        )

    return UnavailableExecutionAdapter(provider, wire_id)


def get_tracking_adapter(
    provider_id: str,
    wires: dict[str, WireConfig] | None,
    env: dict[str, str] | None = None,
    data_path: str | None = None,
):
    """Resolve tracking adapter (TrackingAdapter) for the active wire."""
    del env  # credentials live on wires; tracking stubs do not need env yet
    from .tracking.adapter import get_tracking_adapter as resolve_tracking_adapter

    provider = provider_id.strip().lower()
    wire_id = resolve_active_wire_for(provider, wires, data_path) or get_default_wire_id(
        provider, data_path
    )
    return resolve_tracking_adapter(
        provider,
        wire_id=wire_id,
        data_path=data_path,
    )
