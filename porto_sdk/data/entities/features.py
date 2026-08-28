"""
Features Entity Loader
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...kinds import FeatureKind, parse_feature_kind
from ...requires import Requirement, parse_requires_list
from .base import BaseEntityLoader


@dataclass(frozen=True)
class Feature:
    id: str
    kind: FeatureKind
    name: str
    label: str
    description: str
    requires: tuple[Requirement, ...] = ()
    product_ids: tuple[str, ...] = ()
    zone_ids: tuple[str, ...] = ()


def _parse_feature(row: dict[str, Any]) -> Feature:
    product_ids = row.get("product_ids")
    zone_ids = row.get("zone_ids")
    return Feature(
        id=str(row["id"]),
        kind=parse_feature_kind(row.get("kind"), path="features.kind"),
        name=str(row.get("name") or row["id"]),
        label=str(row.get("label") or row.get("name") or row["id"]),
        description=str(row.get("description") or ""),
        requires=parse_requires_list(row.get("requires"), path="features.requires"),
        product_ids=tuple(str(p) for p in product_ids) if isinstance(product_ids, list) else (),
        zone_ids=tuple(str(z) for z in zone_ids) if isinstance(zone_ids, list) else (),
    )


class FeaturesLoader(BaseEntityLoader):
    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._features: list[Feature] = []

    def load(self, data: dict[str, Any]) -> None:
        self._features = [
            _parse_feature(row) for row in data.get("features", []) if isinstance(row, dict)
        ]

    def get_data(self) -> list[Feature]:
        return self._features

    def get_feature(self, feature_id: str) -> Feature | None:
        return next((f for f in self._features if f.id == feature_id), None)

    def get_features_for_product(self, product_id: str) -> list[Feature]:
        return [item for item in self._features if product_id in item.product_ids]

    def get_features_for_zone(self, zone_id: str) -> list[Feature]:
        return [item for item in self._features if zone_id in item.zone_ids]

    def get_all_features(self) -> list[Feature]:
        return self._features
