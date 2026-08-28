"""Providers subservice — read projection over porto-data."""

import builtins
from typing import TYPE_CHECKING, Any, Optional

from ...adapters.execution_registry import (
    get_default_wire_id,
    list_wire_billing_methods,
    list_wire_execution_methods,
    resolve_active_wire,
    supports_billing,
    supports_execution,
)
from ...data.entities.providers_registry import PortoProvider
from ...data.loader import PortoDataLoader
from ..provider_capabilities import ProviderCapabilitiesService

if TYPE_CHECKING:
    from ...config import PortoConfig


class ProvidersService:
    def __init__(self, data_loader: PortoDataLoader):
        self._loader = data_loader

    def list(self) -> list[PortoProvider]:
        return self._loader.list_providers()

    def can_use_feature(
        self,
        provider: str,
        feature: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        return ProviderCapabilitiesService(self._loader).can(
            provider,
            feature,
            context,  # type: ignore[arg-type]
        )

    def supports_billing(
        self,
        method: str,
        *,
        config: Optional["PortoConfig"] = None,
        wire_id: str | None = None,
    ) -> bool:
        provider = (
            next(iter(sorted(config.configured_provider_ids())), None) if config else None
        ) or self._loader.provider_id
        data_path = (config.data if config else None) or getattr(self._loader, "data_path", None)
        return supports_billing(
            provider,
            method,
            config=config,
            wire_id=wire_id,
            data_path=data_path,
        )

    def supports_execution(
        self,
        method: str,
        *,
        config: Optional["PortoConfig"] = None,
        wire_id: str | None = None,
    ) -> bool:
        provider = (
            next(iter(sorted(config.configured_provider_ids())), None) if config else None
        ) or self._loader.provider_id
        data_path = (config.data if config else None) or getattr(self._loader, "data_path", None)
        return supports_execution(
            provider,
            method,
            config=config,
            wire_id=wire_id,
            data_path=data_path,
        )

    def get_billing_methods(
        self,
        *,
        config: Optional["PortoConfig"] = None,
        wire_id: str | None = None,
    ) -> builtins.list[str]:
        provider = (
            next(iter(sorted(config.configured_provider_ids())), None) if config else None
        ) or self._loader.provider_id
        data_path = (config.data if config else None) or getattr(self._loader, "data_path", None)
        wire = wire_id or (get_default_wire_id(provider, data_path) if not config else None)
        if config and not wire:
            wire = resolve_active_wire(config, data_path)
        if not wire:
            return []
        return list_wire_billing_methods(provider, wire, data_path)

    def get_execution_methods(
        self,
        *,
        config: Optional["PortoConfig"] = None,
        wire_id: str | None = None,
    ) -> builtins.list[str]:
        provider = (
            next(iter(sorted(config.configured_provider_ids())), None) if config else None
        ) or self._loader.provider_id
        data_path = (config.data if config else None) or getattr(self._loader, "data_path", None)
        wire = wire_id or (get_default_wire_id(provider, data_path) if not config else None)
        if config and not wire:
            wire = resolve_active_wire(config, data_path)
        if not wire:
            return []
        return list_wire_execution_methods(provider, wire, data_path)

    def get_zones(self) -> builtins.list[dict[str, Any]]:
        zones = self._loader.get_all_zones()
        return [{"id": z.id, "name": z.name, "country_codes": z.country_codes} for z in zones]

    def get_capabilities(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        del context
        services = self._loader.get_all_services()
        features = self._loader._features_loader.get_data()
        return {
            "provider_id": self._loader.provider_id,
            "zones": self.get_zones(),
            "services": services,
            "features": features,
            "online_supported": True,
        }

    def to_public_dict(self, provider: PortoProvider) -> dict[str, Any]:
        return {
            "id": provider.id,
            "name": provider.name,
            "country": provider.country,
            "mark_types": provider.mark_types,
        }
