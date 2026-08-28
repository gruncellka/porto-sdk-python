"""
Service Resolver - Resolves available services for product and zone.

Resolution primitive: product_id + zone_id -> available services.
`kind` is cross-provider grouping; `id` is the only identifier.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, NoReturn

from ...data.entities.features import Feature
from ...data.entities.products import PortoProduct
from ...data.entities.services import Service
from ...data.loader import PortoDataLoader
from ...errors import PortoError, PortoErrorCode
from ...errors.domains.data import raise_data_not_found
from ...kinds import SERVICE_KINDS, ServiceKind, parse_service_kind

REGISTERED_FEATURE_KINDS = frozenset({"recipient_signature", "acceptance_proof"})


def resolve_service_token(loader: PortoDataLoader, token: str) -> list[Service]:
    """Match catalog services by concrete id (not kind). Kind matching is bind_requested_services."""
    wanted = str(token or "").strip()
    if not wanted:
        return []
    found = loader.get_service(wanted)
    return [found] if found is not None else []


def product_matches_unmatched_kind(
    loader: PortoDataLoader, product: PortoProduct, kind: str
) -> bool:
    """When the provider has no service for ``kind``, match included feature capabilities."""
    token = kind.strip().lower()
    if token == "registered":
        if not product.indemnity:
            return False
        for fid in product.included_features or []:
            feat = loader.get_feature(str(fid))
            if feat and feat.kind in REGISTERED_FEATURE_KINDS:
                return True
        return False
    for fid in product.included_features or []:
        feat = loader.get_feature(str(fid))
        if feat and feat.kind == token:
            return True
    return False


def _feature_kind(feat: Feature | None) -> str:
    return feat.kind if feat is not None else ""


def raise_service_ambiguous(*, kind: ServiceKind, candidates: list[Service]) -> NoReturn:
    raise PortoError(
        f"Multiple service options match kind {kind}",
        PortoErrorCode.PORTO_SERVICE_AMBIGUOUS,
        status_code=400,
        details={
            "kind": kind,
            "candidates": [
                {"id": row.id, "kind": row.kind, "name": row.name, "label": row.label}
                for row in candidates
            ],
        },
        retryable=False,
    )


def raise_service_unsupported(
    *,
    kind: ServiceKind,
    zone_id: str | None = None,
    product_id: str | None = None,
) -> NoReturn:
    details: dict[str, Any] = {"kind": kind}
    if zone_id:
        details["zone_id"] = zone_id
    if product_id:
        details["product_id"] = product_id
    raise PortoError(
        f"Service kind {kind} is not supported in this context",
        PortoErrorCode.PORTO_SERVICE_UNSUPPORTED,
        status_code=400,
        details=details,
        retryable=False,
    )


def bind_requested_services(
    loader: PortoDataLoader,
    *,
    kinds: Sequence[str] | None,
    service_ids: Sequence[str] | None,
    zone_id: str,
    product_id: str | None = None,
) -> tuple[list[str], tuple[ServiceKind, ...], tuple[ServiceKind, ...]]:
    """Bind requested ServiceKind[] plus optional catalog id pins.

    Returns (bound catalog ids, selected kinds). Kind strings in service_ids are invalid.
    Multiple catalog rows for one kind without a pin → PORTO_SERVICE_AMBIGUOUS.
    """
    requested_kinds: list[ServiceKind] = []
    seen_kinds: set[ServiceKind] = set()
    for raw in kinds or []:
        kind = parse_service_kind(raw)
        if kind not in seen_kinds:
            seen_kinds.add(kind)
            requested_kinds.append(kind)

    pins: list[str] = []
    seen_pins: set[str] = set()
    for raw in service_ids or []:
        token = str(raw or "").strip()
        if not token:
            continue
        if token in SERVICE_KINDS:
            raise PortoError(
                "service_ids must be catalog service ids, not kinds",
                PortoErrorCode.PORTO_DATA_INVALID,
                status_code=400,
                details={"service_ids": token, "kind": token},
                retryable=False,
            )
        row = loader.get_service(token)
        if row is None:
            raise_data_not_found(
                f"Service not found: {token}",
                entity_id=token,
            )
            raise AssertionError("unreachable")
        if requested_kinds and row.kind not in seen_kinds:
            raise PortoError(
                f"Service {token} kind {row.kind} is not in requested services",
                PortoErrorCode.PORTO_DATA_INVALID,
                status_code=400,
                details={"service_ids": token, "kind": row.kind},
                retryable=False,
            )
        if token not in seen_pins:
            seen_pins.add(token)
            pins.append(token)

    if pins and not requested_kinds:
        raise PortoError(
            "service_ids require matching services kinds",
            PortoErrorCode.PORTO_DATA_INVALID,
            status_code=400,
            details={"service_ids": pins},
            retryable=False,
        )

    if not requested_kinds:
        return [], (), ()

    pool = loader.get_services_for_zone(zone_id)
    if product_id:
        allowed = {s.id for s in loader.get_services_for_product(product_id)}
        pool = [s for s in pool if s.id in allowed]

    bound: list[str] = []
    unmatched: list[ServiceKind] = []
    for kind in requested_kinds:
        matches = [row for row in pool if row.kind == kind]
        match_ids = {row.id for row in matches}
        pins_for_kind: list[str] = []
        for sid in pins:
            row = loader.get_service(sid)
            if row is not None and row.kind == kind:
                pins_for_kind.append(sid)
        if pins_for_kind:
            missing = [sid for sid in pins_for_kind if sid not in match_ids]
            if missing:
                raise_data_not_found(
                    f"Service not available for product/zone: {missing[0]}",
                    entity_id=missing[0],
                )
            bound.extend(pins_for_kind)
            continue
        if len(matches) == 1:
            bound.append(matches[0].id)
            continue
        if len(matches) > 1:
            raise_service_ambiguous(kind=kind, candidates=matches)
        unmatched.append(kind)

    return bound, tuple(requested_kinds), tuple(unmatched)


def validate_service_selection(
    service_ids: list[str] | None,
    options: list,
) -> None:
    """Catalog-backed gate for add-on service ids (porto-data combinable_with).

    Empty selection is valid. Unknown id → PORTO_DATA_NOT_FOUND.
    Incompatible pair → PORTO_SERVICES_INCOMPATIBLE.
    ``options`` is the product×zone ServiceOption list.
    """
    unique: list[str] = []
    seen: set[str] = set()
    for raw in service_ids or []:
        sid = str(raw or "").strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        unique.append(sid)
    if not unique:
        return

    by_id = {str(row.id): row for row in options}
    for sid in unique:
        if sid not in by_id:
            raise_data_not_found(
                f"Service not available for product/zone: {sid}",
                entity_id=sid,
            )

    conflicts: list[list[str]] = []
    for i, left_id in enumerate(unique):
        for right_id in unique[i + 1 :]:
            a = by_id[left_id]
            b = by_id[right_id]
            a_list = a.combinable_with
            b_list = b.combinable_with
            a_ok = a_list is None or right_id in a_list
            b_ok = b_list is None or left_id in b_list
            if not a_ok or not b_ok:
                conflicts.append([left_id, right_id])

    if conflicts:
        raise PortoError(
            "Selected services are not combinable",
            PortoErrorCode.PORTO_SERVICES_INCOMPATIBLE,
            status_code=422,
            details={"service_ids": unique, "conflicts": conflicts},
            retryable=False,
        )


class ServiceResolver:
    """Resolves available services for product and zone."""

    def __init__(self, loader: PortoDataLoader):
        self._loader = loader

    def resolve(self, product_id: str, zone_id: str) -> dict:
        services = self._loader.get_services_for_product(product_id)
        zone_services = self._loader.get_services_for_zone(zone_id)
        zone_ids = {zs.id for zs in zone_services}
        available = [s for s in services if s.id in zone_ids]
        return {"is_valid": True, "data": {"services": available}}
