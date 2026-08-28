from porto_sdk.data.graph_normalize import normalize_resolution_graph
from porto_sdk.services.mark_resolution import resolve_mark_profile_id


def test_normalize_edges_products_to_links():
    graph = normalize_resolution_graph(
        {
            "file_type": "graph",
            "unit": {"weight": "g"},
            "dependencies": {},
            "edges": {
                "products": {
                    "standardbrief": {
                        "zones": ["domestic", "world"],
                        "weight_tiers": ["W0020"],
                    }
                },
                "marks": {
                    "domestic": {
                        "profile": "domestic",
                        "services": {"einschreiben": "registered"},
                    }
                },
            },
            "services": ["einschreiben"],
        }
    )
    assert graph.links["standardbrief"]["zones"] == ["domestic", "world"]
    assert graph.mark_edges["domestic"]["profile"] == "domestic"
    assert graph.services == ["einschreiben"]
    assert graph.strategy is None
    assert graph.wire_edges == {}


def test_normalize_wire_edges_and_strategy():
    graph = normalize_resolution_graph(
        {
            "file_type": "graph",
            "unit": {},
            "dependencies": {},
            "strategy": "service",
            "edges": {
                "products": {
                    "standardbrief": {
                        "zones": ["domestic"],
                        "weight_tiers": ["W0020"],
                    }
                },
                "wire": {
                    "internetmarke": {
                        "standardbrief": {
                            "domestic": {"base": 1},
                        }
                    }
                },
            },
        }
    )
    assert graph.strategy == "service"
    assert graph.wire_edges["internetmarke"]["standardbrief"]["domestic"]["base"] == 1


def test_resolve_mark_profile_with_service_override():
    mark_edges = {
        "domestic": {
            "profile": "domestic",
            "services": {"einschreiben": "registered"},
        }
    }
    assert (
        resolve_mark_profile_id(
            mark_edges=mark_edges,
            zone_id="domestic",
            service_ids=None,
            default_profile_id="domestic",
        )
        == "domestic"
    )
    assert (
        resolve_mark_profile_id(
            mark_edges=mark_edges,
            zone_id="domestic",
            service_ids=["einschreiben"],
            default_profile_id="domestic",
        )
        == "registered"
    )
