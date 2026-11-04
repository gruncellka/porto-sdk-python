"""Purchased FeatureKind values from bound catalog services."""

from __future__ import annotations

from typing import Any, Sequence

from ..errors.domains.data import raise_data_invalid
from ..kinds import FeatureKind


def feature_kinds_for_service_ids(
    loader: Any,
    service_ids: Sequence[str] | None,
) -> list[FeatureKind]:
    """Catalog order. Duplicate kinds collapse. Missing feature id fails closed."""
    kinds: list[FeatureKind] = []
    seen: set[str] = set()
    for raw in service_ids or []:
        service_id = str(raw or "").strip()
        if not service_id:
            continue
        service = loader.get_service(service_id)
        if service is None:
            raise_data_invalid(
                f"Unknown service: {service_id}",
                path="services",
                details={"service_id": service_id},
            )
        for feature_id in service.features:
            fid = str(feature_id).strip()
            if not fid:
                continue
            feature = loader.get_feature(fid)
            if feature is None:
                raise_data_invalid(
                    f"Unknown feature: {fid}",
                    path="services.features",
                    details={"service_id": service_id, "feature_id": fid},
                )
            kind = feature.kind
            if kind in seen:
                continue
            seen.add(kind)
            kinds.append(kind)
    return kinds
