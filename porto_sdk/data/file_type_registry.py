"""Metadata-driven dispatch from porto-data file_type to entity loaders."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .loader import PortoDataLoader

# file_type values that are validated but have no entity payload to load
_SKIP_FILE_TYPES = frozenset({"graph", "execution", "integrations", "integration"})


@dataclass
class _DispatchResult:
    handled: bool
    skipped: bool = False


class FileTypeRegistry:
    """Routes validated porto-data payloads to entity loaders."""

    def __init__(self, loader: PortoDataLoader) -> None:
        self._loader = loader
        self._handlers: dict[str, Callable[[dict[str, Any]], None]] = {
            "products": loader._products_loader.load,
            "zones": loader._zones_loader.load,
            "weight_tiers": self._load_weight_tiers,
            "weights": self._load_weights,
            "prices": loader._prices_loader.load,
            "product_prices": self._load_product_prices,
            "service_prices": self._load_service_prices,
            "dimensions": loader._dimensions_loader.load,
            "features": loader._features_loader.load,
            "services": loader._services_loader.load,
            "restrictions": loader._restrictions_loader.load,
            "envelopes": loader._envelopes_loader.load,
            "layouts": loader._layouts_loader.load,
            "addresses": loader._addresses_loader.load,
            "marks": loader._marks_loader.load,
            "providers": loader._providers_loader.load,
            "markets": loader._markets_loader.load,
            "jurisdictions": loader._jurisdictions_loader.load,
            "provider_rules": loader._rules_loader.load,
        }

    def dispatch(self, file_type: str, data: dict[str, Any]) -> _DispatchResult:
        if file_type in _SKIP_FILE_TYPES:
            return _DispatchResult(handled=True, skipped=True)
        handler = self._handlers.get(file_type)
        if handler is None:
            return _DispatchResult(handled=False)
        handler(data)
        return _DispatchResult(handled=True)

    def _load_weights(self, data: dict[str, Any]) -> None:
        normalized = {
            **data,
            "weight_tiers": data.get("weights") or data.get("weight_tiers"),
            "file_type": "weight_tiers",
        }
        self._loader._weight_tiers_loader.load(normalized)

    def _load_weight_tiers(self, data: dict[str, Any]) -> None:
        self._loader._weight_tiers_loader.load(data)

    def _load_product_prices(self, data: dict[str, Any]) -> None:
        normalized = {
            "file_type": "prices",
            "unit": data.get("unit", {}),
            "prices": {"product_prices": data.get("product_prices", [])},
        }
        self._loader._prices_loader.load(normalized)

    def _load_service_prices(self, data: dict[str, Any]) -> None:
        self._loader._prices_loader.load_service_prices(data)
