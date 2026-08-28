"""Resolve mark profile id from graph.edges.marks + selected services."""

from __future__ import annotations

from typing import Any


def resolve_mark_profile_id(
    *,
    mark_edges: dict[str, dict[str, Any]],
    zone_id: str | None,
    service_ids: list[str] | None,
    default_profile_id: str | None,
) -> str | None:
    if not zone_id:
        return default_profile_id

    zone_edge = mark_edges.get(zone_id) or {}
    profile_id = zone_edge.get("profile") or default_profile_id
    service_map = zone_edge.get("services") or {}

    for service_id in service_ids or []:
        override = service_map.get(service_id)
        if override:
            profile_id = override

    return profile_id
