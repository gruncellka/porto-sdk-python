"""
Services Entity Loader
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...kinds import ServiceKind, parse_service_kind
from ...requires import Requirement, parse_requires_list
from .base import BaseEntityLoader


@dataclass(frozen=True)
class Service:
    id: str
    kind: ServiceKind
    name: str
    label: str
    description: str
    features: tuple[str, ...]
    requires: tuple[Requirement, ...] = ()
    supported_zones: tuple[str, ...] = ()
    combinable_with: tuple[str, ...] | None = None
    product_ids: tuple[str, ...] = ()


def _parse_service(row: dict[str, Any]) -> Service:
    combinable = row.get("combinable_with")
    product_ids = row.get("product_ids")
    return Service(
        id=str(row["id"]),
        kind=parse_service_kind(row.get("kind"), path="services.kind"),
        name=str(row.get("name") or row["id"]),
        label=str(row.get("label") or row.get("name") or row["id"]),
        description=str(row.get("description") or ""),
        features=tuple(str(fid) for fid in (row.get("features") or []) if fid),
        requires=parse_requires_list(row.get("requires"), path="services.requires"),
        supported_zones=tuple(str(z) for z in (row.get("supported_zones") or []) if z),
        combinable_with=tuple(str(s) for s in combinable) if isinstance(combinable, list) else None,
        product_ids=tuple(str(p) for p in product_ids) if isinstance(product_ids, list) else (),
    )


class ServicesLoader(BaseEntityLoader):
    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._services: list[Service] = []

    def load(self, data: dict[str, Any]) -> None:
        self._services = [
            _parse_service(row) for row in data.get("services", []) if isinstance(row, dict)
        ]

    def get_data(self) -> list[Service]:
        return self._services

    def get_service(self, service_id: str) -> Service | None:
        return next((s for s in self._services if s.id == service_id), None)

    def get_services_for_product(self, product_id: str) -> list[Service]:
        result: list[Service] = []
        for item in self._services:
            if not item.product_ids or product_id in item.product_ids:
                result.append(item)
        return result

    def get_services_for_zone(self, zone_id: str) -> list[Service]:
        result: list[Service] = []
        for service in self._services:
            if not service.supported_zones or zone_id in service.supported_zones:
                result.append(service)
        return result

    def get_all_services(self) -> list[Service]:
        return self._services
