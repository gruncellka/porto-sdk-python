"""ExecutionBinding — how a postal decision can be executed (wire + mark profile).

Consumes Porto / product+zone facts. Must not re-select product or price.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..data.loader import PortoDataLoader
from .mark_resolution import resolve_mark_profile_id
from .wire_resolution import WireCode, resolve_wire_code


@dataclass(frozen=True)
class ExecutionBindingResult:
    wire_code: WireCode
    mark_profile_id: str | None


class ExecutionBinding:
    """Stage-2 binding: Porto (+ active wire) → wire_code + mark_profile."""

    def __init__(self, data_loader: PortoDataLoader):
        self._loader = data_loader

    def resolve_wire_code(
        self,
        *,
        wire: str,
        product_id: str,
        zone_id: str,
        service_ids: list[str] | None = None,
    ) -> WireCode:
        graph = self._loader.resolution_graph
        return resolve_wire_code(
            wire_edges=graph.wire_edges,
            strategy=graph.strategy,
            wire=wire,
            product_id=product_id,
            zone_id=zone_id,
            service_ids=service_ids,
        )

    def resolve_mark_profile_id(
        self,
        *,
        zone_id: str | None = None,
        service_ids: list[str] | None = None,
    ) -> str | None:
        graph = self._loader.resolution_graph
        default = self._loader.get_default_mark_profile()
        default_id = default.id if default else None
        return resolve_mark_profile_id(
            mark_edges=graph.mark_edges,
            zone_id=zone_id,
            service_ids=service_ids,
            default_profile_id=default_id,
        )

    def bind(
        self,
        *,
        wire: str,
        product_id: str,
        zone_id: str,
        service_ids: list[str] | None = None,
    ) -> ExecutionBindingResult:
        return ExecutionBindingResult(
            wire_code=self.resolve_wire_code(
                wire=wire,
                product_id=product_id,
                zone_id=zone_id,
                service_ids=service_ids,
            ),
            mark_profile_id=self.resolve_mark_profile_id(
                zone_id=zone_id,
                service_ids=service_ids,
            ),
        )
