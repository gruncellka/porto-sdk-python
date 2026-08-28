"""Normalize porto-data graph.json (edges.products/marks) into SDK ResolutionGraph."""

from __future__ import annotations

from typing import Any

from .types import ResolutionGraph


def normalize_resolution_graph(data: dict[str, Any]) -> ResolutionGraph:
    edges = data.get("edges") or {}
    products = edges.get("products")
    links: dict[str, dict[str, list[str]]] = products if isinstance(products, dict) else {}

    marks = edges.get("marks")
    mark_edges: dict[str, dict[str, Any]] = marks if isinstance(marks, dict) else {}

    wire = edges.get("wire")
    wire_edges: dict[str, dict[str, dict[str, dict[str, Any]]]] = (
        wire if isinstance(wire, dict) else {}
    )
    services = list(data.get("services") or [])
    strategy = data.get("strategy")
    if strategy is not None:
        strategy = str(strategy)

    return ResolutionGraph(
        file_type=str(data.get("file_type", "graph")),
        unit=dict(data.get("unit") or {}),
        dependencies=dict(data.get("dependencies") or {}),
        links=links,
        mark_edges=mark_edges,
        wire_edges=wire_edges,
        services=services,
        strategy=strategy,
        lookup_rules=dict(data.get("lookup_rules") or {}),
        global_settings=dict(data.get("global_settings") or {}),
    )
