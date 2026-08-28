"""Thin catalog/loader façade for resolution catalog reads."""

from __future__ import annotations

from typing import Any

from ...data.entities.services import Service
from ...data.loader import PortoDataLoader, PortoPricing, PortoProduct, PortoWeightTier, PortoZone
from ...errors.domains.data import raise_data_not_found
from ...kinds import ServiceKind
from ..product_option_types import ServiceOption
from .service_resolver import ServiceResolver
from .types import DestinationCountry


class PortoCatalog:
    """Catalog reads over PortoDataLoader — no resolve() orchestration."""

    def __init__(self, loader: PortoDataLoader, service_resolver: ServiceResolver | None = None):
        self._loader = loader
        self._service_resolver = service_resolver or ServiceResolver(loader)

    def list_products(
        self,
        country_from: str | None = None,
        country_to: str | None = None,
    ) -> list[PortoProduct]:
        del country_from, country_to
        return self._loader.get_all_products()

    def get_product(self, product_id: str) -> PortoProduct | None:
        return self._loader.get_product(product_id)

    def get_product_constraints(self, product_id: str) -> dict[str, Any]:
        product = self._loader.get_product(product_id)
        if product is None:
            raise_data_not_found(
                f"Product not found: {product_id}",
                entity_id=product_id,
            )
            raise AssertionError("unreachable")
        tier = (
            self._loader.get_weight_tier(product.weight_tier) if product.weight_tier else None
        )
        max_weight = tier.max_weight if tier else None
        if max_weight is None:
            links = getattr(self._loader.resolution_graph, "links", {}) or {}
            link = links.get(product.id) if isinstance(links, dict) else None
            tier_ids: list[Any] = []
            if isinstance(link, dict):
                tier_ids = link.get("weight_tiers") or []
            max_seen = 0
            for tier_id in tier_ids:
                wt = self._loader.get_weight_tier(tier_id)
                if wt is not None and getattr(wt, "max_weight", 0) > max_seen:
                    max_seen = wt.max_weight
            max_weight = max_seen if max_seen > 0 else None
        return {
            "product_id": product.id,
            "allowed_envelope_ids": list(product.envelope_ids),
            "min_weight": 0,
            "max_weight": max_weight,
        }

    def get_graph(self) -> dict[str, Any]:
        graph = self._loader.resolution_graph
        return {
            "links": getattr(graph, "links", {}),
            "unit": getattr(graph, "unit", {}),
        }

    def list_destination_countries(self) -> list[DestinationCountry]:
        by_code: dict[str, str] = {}
        for zone in self._loader.get_all_zones():
            for raw_code in zone.country_codes:
                code = raw_code.strip().upper()
                if len(code) == 2 and code not in by_code:
                    by_code[code] = zone.id
        return [
            DestinationCountry(code=code, zone_id=zone_id)
            for code, zone_id in sorted(by_code.items())
        ]

    def list_zones(self) -> list[PortoZone]:
        return self._loader.get_all_zones()

    def list_dimensions(self) -> list[dict[str, Any]]:
        return self._loader.get_all_dimensions()

    def list_envelopes(self) -> list:
        return self._loader.list_envelopes()

    def list_weight_tiers(self) -> list[PortoWeightTier]:
        return self._loader.get_all_weight_tiers()

    def get_weight_tier(self, weight_tier_id: str) -> PortoWeightTier | None:
        return self._loader.get_weight_tier(weight_tier_id)

    def get_price_by_product_zone_weight_tier(
        self, product_id: str, zone_id: str, weight_tier_id: str
    ) -> PortoPricing | None:
        return self._loader.get_price_by_product_zone_weight_tier(
            product_id, zone_id, weight_tier_id
        )

    def get_service_price(self, service_id: str, zone_id: str | None = None) -> int | None:
        return self._loader.get_service_price(service_id, zone_id)

    def get_service(self, service_id: str) -> Service | None:
        return self._loader.get_service(service_id)

    def services_of_kind(self, kind: ServiceKind) -> list[Service]:
        return [row for row in self._loader.get_all_services() if row.kind == kind]

    def list_service_options_for_product_zone(
        self, product_id: str, zone_id: str
    ) -> list[ServiceOption]:
        product = self.get_product(product_id)
        if product is None:
            return []

        graph = self.get_graph()
        unit = graph.get("unit", {}) if isinstance(graph, dict) else {}
        currency = "EUR"
        if isinstance(unit, dict) and unit.get("currency"):
            currency = str(unit["currency"]).upper()

        resolved = self._service_resolver.resolve(product_id, zone_id)
        rows = (resolved.get("data") or {}).get("services") or []
        options: list[ServiceOption] = []
        for row in rows:
            sid = row.id
            price = self.get_service_price(sid, zone_id)
            options.append(
                ServiceOption(
                    id=sid,
                    name=row.name or sid,
                    label=getattr(row, "label", None),
                    kind=getattr(row, "kind", None),
                    amount=price,
                    currency=currency,
                    combinable_with=(
                        list(row.combinable_with) if row.combinable_with is not None else None
                    ),
                )
            )
        return options

    def list_wire_ids(self) -> list[str]:
        graph = self._loader.resolution_graph
        return sorted(graph.wire_edges.keys())
