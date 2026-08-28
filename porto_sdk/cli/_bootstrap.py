"""
CLI bootstrap. Single entry point: env + file + flags merge → { config, provider, wire }.
All commands receive this; no direct config loading in commands.
"""

import argparse
from typing import Any, NamedTuple

from ..client import PortoClient
from ._config_store import load_porto_config
from .integrations.registry import get_default_wire


class BootstrapResult(NamedTuple):
    config: Any
    provider: str
    wire: str


def bootstrap(args: argparse.Namespace | None = None) -> BootstrapResult:
    """Single bootstrap entry point. Returns { config, provider, wire }."""
    provider_override = getattr(args, "provider", None) if args else None
    config = load_porto_config(provider_override=provider_override)
    ids = config.configured_provider_ids()
    raw = provider_override or next(iter(sorted(ids)), "deutschepost")
    provider = str(raw).strip().lower()
    wire = (getattr(args, "wire", None) if args else None) or get_default_wire(provider)
    wire = str(wire).strip().lower()
    return BootstrapResult(config=config, provider=provider, wire=wire)


def resolve_provider(args: argparse.Namespace | None) -> str | None:
    """Provider from args (--provider) or None for config resolution."""
    return getattr(args, "provider", None) if args else None


def build_cli_config(args: argparse.Namespace) -> Any:
    """Resolve provider, load file, merge env, return PortoConfig."""
    return load_porto_config(provider_override=resolve_provider(args))


def build_cli_client(args: argparse.Namespace) -> PortoClient:
    """Build config and create PortoClient."""
    return PortoClient(build_cli_config(args))


def bound_cli_provider(args: argparse.Namespace):
    """CLI bound provider — always an explicit id from bootstrap."""
    boot = bootstrap(args)
    return PortoClient(boot.config).provider(boot.provider)
