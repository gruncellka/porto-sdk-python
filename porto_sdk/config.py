"""
Configuration for Porto SDK

Integration-agnostic. No provider/wire specifics.
Provider/wire bootstrap lives in the adapter layer.

PortoConfig is user/env input. Downstream runtime uses NormalizedPortoConfig only.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ids import as_provider_id
from .time import parse_duration

DEFAULT_PROVIDER: Final[str] = "deutschepost"
"""Internal catalog bootstrap id. Not a root export and not a PortoConfig field."""


def normalize_provider_id(provider_id: str) -> str:
    return str(as_provider_id(provider_id))


def _coerce_duration(value: object) -> timedelta:
    if isinstance(value, timedelta):
        return parse_duration(value)
    if isinstance(value, (int, float)):
        return parse_duration(value)
    raise TypeError(f"duration must be seconds or timedelta, got {type(value).__name__}")


class CacheConfig(BaseModel):
    model_config = ConfigDict(ser_json_timedelta="float")

    enabled: bool = True
    ttl: timedelta = timedelta(seconds=300)
    max_size: int = 1000

    @field_validator("ttl", mode="before")
    @classmethod
    def _coerce_ttl(cls, value: object) -> object:
        if isinstance(value, (int, float, timedelta)):
            return _coerce_duration(value)
        return value


class WireConfig(BaseModel):
    """Generic wire config. Adapter bootstrap populates this."""

    base_url: str | None = None
    credentials: dict[str, str] | None = None


class TransportConfig(BaseModel):
    """HTTP transport policy. Timeouts and backoff are seconds."""

    model_config = ConfigDict(ser_json_timedelta="float")

    timeout: timedelta = timedelta(seconds=30)
    retries: int = 3
    backoff: timedelta = timedelta(milliseconds=100)

    @field_validator("timeout", "backoff", mode="before")
    @classmethod
    def _duration_fields(cls, value: object) -> object:
        if isinstance(value, (int, float, timedelta)):
            return _coerce_duration(value)
        return value


class ProviderRuntimeConfig(BaseModel):
    """Per-provider execution context: wires and auth for one carrier."""

    wires: dict[str, WireConfig] | None = None


class NormalizedPortoConfig(BaseModel):
    """Complete internal runtime contract. Downstream constructors take only this."""

    model_config = ConfigDict(frozen=True)

    default_provider: str
    providers: dict[str, ProviderRuntimeConfig]
    allowlist: frozenset[str] | None = None
    data: str | None = None
    cache: CacheConfig
    transport: TransportConfig
    strict_data_validation: bool = True

    def configured_provider_ids(self) -> frozenset[str]:
        return frozenset(self.providers.keys())

    def resolved_transport(self) -> TransportConfig:
        return self.transport

    def runtime_for(self, provider_id: str) -> ProviderRuntimeConfig:
        pid = normalize_provider_id(provider_id)
        return self.providers.get(pid) or ProviderRuntimeConfig(wires=None)

    def wires_for(self, provider_id: str) -> dict[str, WireConfig] | None:
        return self.runtime_for(provider_id).wires


class PortoConfig(BaseModel):
    """
    Porto SDK Configuration (user/env input).

    Canonical shape: providers.<id>.wires, data, cache, transport.
    There is no default provider field — ``client.provider(id)`` is always explicit.
    """

    providers: dict[str, ProviderRuntimeConfig] | None = Field(
        default=None,
        description="Per-provider execution configs (wires, auth).",
    )
    data: str | None = Field(
        default=None,
        description="Path to porto-data directory. If None, registry discovers from package.",
    )
    cache: CacheConfig | None = None
    transport: TransportConfig | None = None
    strict_data_validation: bool = Field(
        default=True,
        description="When False, skip strict porto-data schema validation (relaxed dev/vend).",
    )

    @model_validator(mode="after")
    def _normalize_registry(self) -> PortoConfig:
        if self.providers:
            normalized: dict[str, ProviderRuntimeConfig] = {}
            for provider_id, runtime in self.providers.items():
                normalized[normalize_provider_id(provider_id)] = runtime
            object.__setattr__(self, "providers", normalized)
        if self.transport is None:
            object.__setattr__(self, "transport", TransportConfig())
        if self.data and self.providers:
            from .data.porto_data_registry import get_valid_providers_from_mappings

            mappings = Path(self.data) / "mappings.json"
            if mappings.is_file():
                valid = get_valid_providers_from_mappings(self.data)
                unknown = set(self.providers) - valid if valid else set()
                if unknown:
                    raise ValueError(
                        f"Invalid provider(s) {sorted(unknown)}. Valid: {sorted(valid)}"
                    )
        return self

    def normalize(self) -> NormalizedPortoConfig:
        """Fill defaults, canonicalize units. Parse env once via from_env."""
        if self.providers is None:
            providers: dict[str, ProviderRuntimeConfig] = {}
            allowlist: frozenset[str] | None = None
        else:
            providers = dict(self.providers)
            allowlist = frozenset(providers.keys())
        catalog = next(iter(sorted(providers.keys())), DEFAULT_PROVIDER)
        return NormalizedPortoConfig(
            default_provider=catalog,
            providers=providers,
            allowlist=allowlist,
            data=self.data,
            cache=self.cache or CacheConfig(),
            transport=self.transport or TransportConfig(),
            strict_data_validation=self.strict_data_validation,
        )

    def configured_provider_ids(self) -> frozenset[str]:
        return self.normalize().configured_provider_ids()

    def resolved_transport(self) -> TransportConfig:
        return self.normalize().transport

    def runtime_for(self, provider_id: str) -> ProviderRuntimeConfig:
        return self.normalize().runtime_for(provider_id)

    def wires_for(self, provider_id: str) -> dict[str, WireConfig] | None:
        return self.normalize().wires_for(provider_id)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> PortoConfig:
        """Load generic config from environment."""
        e = env if env is not None else os.environ
        config: dict[str, object] = {}
        if v := e.get("PORTO_PROVIDER"):
            pid = normalize_provider_id(v.strip())
            config["providers"] = {pid: ProviderRuntimeConfig(wires=None)}
        if v := e.get("PORTO_DATA_PATH"):
            config["data"] = v.strip()
        transport: dict[str, object] = {}
        timeout = e.get("PORTO_TIMEOUT")
        if timeout:
            transport["timeout"] = float(timeout)
        if v := e.get("PORTO_RETRIES"):
            transport["retries"] = int(v)
        if transport:
            config["transport"] = TransportConfig(**transport)
        return cls(**config)
