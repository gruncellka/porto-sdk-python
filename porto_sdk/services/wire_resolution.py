"""Resolve adapter wire codes from graph.edges.wire."""

from __future__ import annotations

from typing import Any

from ..errors import PortoError, PortoErrorCode

WireCode = int | str


def resolve_wire_code(
    *,
    wire_edges: dict[str, dict[str, dict[str, dict[str, Any]]]],
    strategy: str | None,
    wire: str,
    product_id: str,
    zone_id: str,
    service_ids: list[str] | None = None,
) -> WireCode:
    """Look up adapter catalog code for product × zone × optional services."""
    wire_entry = wire_edges.get(wire)
    if not wire_entry:
        raise PortoError(
            f"No wire edges for wire '{wire}'",
            PortoErrorCode.PORTO_PRODUCT_NOT_FOUND,
            status_code=422,
            details={
                "wire": wire,
                "product_id": product_id,
                "zone_id": zone_id,
            },
            retryable=False,
        )

    product_wire = wire_entry.get(product_id)
    if not product_wire:
        raise PortoError(
            f"No wire edge for product '{product_id}' on wire '{wire}'",
            PortoErrorCode.PORTO_PRODUCT_NOT_FOUND,
            status_code=422,
            details={
                "wire": wire,
                "product_id": product_id,
                "zone_id": zone_id,
            },
            retryable=False,
        )

    zone_entry = product_wire.get(zone_id)
    if not isinstance(zone_entry, dict):
        raise PortoError(
            f"No wire edge for product '{product_id}' in zone '{zone_id}'",
            PortoErrorCode.PORTO_PRODUCT_NOT_FOUND,
            status_code=422,
            details={
                "wire": wire,
                "product_id": product_id,
                "zone_id": zone_id,
            },
            retryable=False,
        )

    wire_code: WireCode | None = None
    if strategy == "service" and service_ids:
        service_map = zone_entry.get("services") or {}
        if isinstance(service_map, dict):
            for service_id in service_ids:
                candidate = service_map.get(service_id)
                if candidate is not None:
                    wire_code = candidate

    if wire_code is None:
        wire_code = zone_entry.get("base")

    if wire_code is None:
        raise PortoError(
            "Wire code missing for valid product/zone combination",
            PortoErrorCode.PORTO_PRODUCT_NOT_FOUND,
            status_code=422,
            details={
                "wire": wire,
                "product_id": product_id,
                "zone_id": zone_id,
                "service_ids": service_ids or [],
                "strategy": strategy,
            },
            retryable=False,
        )

    return wire_code
