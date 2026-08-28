"""
Data types for Porto SDK data layer
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResolutionGraph:
    """
    Resolution graph model — porto-data graph.json (file_type graph).

    - dependencies: file loading order
    - links: product × zone × weight_tier (from edges.products)
    - mark_edges: zone → profile + service overrides (edges.marks)
    - services: native service ids declared on the graph
    """

    file_type: str
    unit: dict[str, str]
    dependencies: dict[str, dict[str, Any]]
    links: dict[str, dict[str, list[str]]]
    mark_edges: dict[str, dict[str, Any]] = field(default_factory=dict)
    wire_edges: dict[str, dict[str, dict[str, dict[str, Any]]]] = field(default_factory=dict)
    services: list[str] = field(default_factory=list)
    strategy: str | None = None
    lookup_rules: dict[str, str] = field(default_factory=dict)
    global_settings: dict[str, Any] = field(default_factory=dict)
