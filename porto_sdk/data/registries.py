from dataclasses import dataclass
from typing import Any


@dataclass
class PortoDataRegistries:
    dimensions: list[dict[str, Any]]
    products: list[Any]
    prices: list[Any]
    zones: list[Any]
    weight_tiers: list[Any]
    services: list[dict[str, Any]]
    features: list[dict[str, Any]]
    restrictions: list[dict[str, Any]]
    resolution_graph: Any
    service_prices: list[dict[str, Any]]
