"""Tests for graph.edges.wire resolution across providers."""

from porto_sdk.config import CacheConfig
from porto_sdk.data.context import PostalResolutionContext
from porto_sdk.data.domain_validator import DomainIds
from porto_sdk.data.loader import PortoDataLoader
from porto_sdk.services.execution_binding import ExecutionBinding
from porto_sdk.services.porto_resolver import PortoResolver
from porto_sdk.services.wire_resolution import resolve_wire_code


def _resolver(porto_data_path: str, provider: str) -> PortoResolver:
    loader = PortoDataLoader(porto_data_path, provider=provider)
    validator = DomainIds(loader)
    ctx = PostalResolutionContext(loader=loader, provider_id=provider)
    return PortoResolver(ctx, validator, CacheConfig(enabled=False))


class TestWireResolutionDeutschePost:
    def test_base_code_domestic(self, porto_data_path):
        loader = PortoDataLoader(porto_data_path, provider="deutschepost")
        graph = loader.resolution_graph
        assert graph.strategy == "service"
        code = resolve_wire_code(
            wire_edges=graph.wire_edges,
            strategy=graph.strategy,
            wire="internetmarke",
            product_id="standardbrief",
            zone_id="domestic",
        )
        assert code == 1

    def test_service_einschreiben(self, porto_data_path):
        loader = PortoDataLoader(porto_data_path, provider="deutschepost")
        graph = loader.resolution_graph
        code = resolve_wire_code(
            wire_edges=graph.wire_edges,
            strategy=graph.strategy,
            wire="internetmarke",
            product_id="standardbrief",
            zone_id="domestic",
            service_ids=["einschreiben"],
        )
        assert code == 1007

    def test_execution_binding_resolve_wire_code(self, porto_data_path):
        loader = PortoDataLoader(porto_data_path, provider="deutschepost")
        binding = ExecutionBinding(loader)
        code = binding.resolve_wire_code(
            wire="internetmarke",
            product_id="kompaktbrief",
            zone_id="zone_1_eu",
            service_ids=["einschreiben"],
        )
        assert code == 11016


class TestWireResolutionUkrposhta:
    def test_string_base_code(self, porto_data_path):
        loader = PortoDataLoader(porto_data_path, provider="ukrposhta")
        graph = loader.resolution_graph
        assert graph.strategy == "min"
        code = resolve_wire_code(
            wire_edges=graph.wire_edges,
            strategy=graph.strategy,
            wire="ukrposhta_ecom",
            product_id="lyst_standartnyi",
            zone_id="domestic",
        )
        assert code == "letter"


class TestWireResolutionLaPoste:
    def test_strategy_id(self, porto_data_path):
        loader = PortoDataLoader(porto_data_path, provider="laposte")
        graph = loader.resolution_graph
        assert graph.strategy == "id"

    def test_wire_base_equals_product_id(self, porto_data_path):
        loader = PortoDataLoader(porto_data_path, provider="laposte")
        graph = loader.resolution_graph
        wire = graph.wire_edges["mon_timbre_en_ligne"]
        for product_id, zones in wire.items():
            for zone_id, entry in zones.items():
                assert entry["base"] == product_id, (
                    f"wire base must equal products.id for strategy id: {product_id}/{zone_id}"
                )

    def test_all_purchasable_products_wired(self, porto_data_path):
        loader = PortoDataLoader(porto_data_path, provider="laposte")
        graph = loader.resolution_graph
        product_ids = {p.id for p in loader.get_all_products()}
        graph_ids = set(graph.links.keys())
        wire_ids = set(graph.wire_edges["mon_timbre_en_ligne"].keys())
        assert product_ids == graph_ids
        assert product_ids == wire_ids

    def test_resolve_lettre_recommandee_r_un(self, porto_data_path):
        loader = PortoDataLoader(porto_data_path, provider="laposte")
        graph = loader.resolution_graph
        code = resolve_wire_code(
            wire_edges=graph.wire_edges,
            strategy=graph.strategy,
            wire="mon_timbre_en_ligne",
            product_id="lettre_recommandee_r_un",
            zone_id="domestic",
        )
        assert code == "lettre_recommandee_r_un"


class TestPortoResolverWireApi:
    def test_list_wire_ids_deutschepost(self, porto_data_path):
        resolver = _resolver(porto_data_path, "deutschepost")
        assert resolver.list_wire_ids() == ["internetmarke"]

    def test_resolve_wire_code_via_execution_binding(self, porto_data_path):
        loader = PortoDataLoader(porto_data_path, provider="deutschepost")
        binding = ExecutionBinding(loader)
        code = binding.resolve_wire_code(
            wire="internetmarke",
            product_id="standardbrief",
            zone_id="domestic",
            service_ids=["einschreiben"],
        )
        assert code == 1007


class TestWireResolutionSwissPost:
    def test_catalog_key_base(self, porto_data_path):
        loader = PortoDataLoader(porto_data_path, provider="swisspost")
        graph = loader.resolution_graph
        code = resolve_wire_code(
            wire_edges=graph.wire_edges,
            strategy=graph.strategy,
            wire="webstamp",
            product_id="a_post_standardbrief",
            zone_id="domestic",
        )
        assert code == "a_post_standardbrief"

    def test_graph_loads_webstamp_wire(self, porto_data_path):
        loader = PortoDataLoader(porto_data_path, provider="swisspost")
        graph = loader.resolution_graph
        assert graph.strategy == "speed"
        assert "webstamp" in graph.wire_edges
