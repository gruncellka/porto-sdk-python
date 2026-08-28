"""Layout join — face + optional window + optional mark. No invented defaults."""

from porto_sdk import PortoClient, PortoConfig
from porto_sdk.config import ProviderRuntimeConfig
from porto_sdk.errors import PortoError, PortoErrorCode
from tests.support.porto_features_path import get_porto_data_path


def _client(provider: str) -> PortoClient:
    return PortoClient(
        PortoConfig(
            providers={provider: ProviderRuntimeConfig()},
            data=get_porto_data_path(),
            strict_data_validation=False,
        )
    )


def test_c5_de_layout_window_and_mark_facts() -> None:
    layout = _client("deutschepost").envelopes.layout(
        "C5",
        "DE",
        "standardbrief",
        zone_id="domestic",
    )
    assert "restricted_areas" not in layout
    assert "has_window" not in layout
    assert layout["width"] == 229
    assert layout["height"] == 162
    assert layout["window"] == {"x": 20, "y": 57, "width": 90, "height": 45}
    assert layout["mark"]["type"] == "stamp"
    assert layout["mark"]["size"] == {"width": 37, "height": 20}
    assert layout["mark"]["placement"] == {"x": 155, "y": 0, "width": 74, "height": 40}


def test_get_mark_returns_size_and_placement() -> None:
    mark = _client("deutschepost").envelopes.get_mark(
        "standardbrief",
        envelope_id="C5",
        zone_id="domestic",
    )
    assert mark["type"] == "stamp"
    assert mark["size"] == {"width": 37, "height": 20}
    assert mark["placement"] == {"x": 155, "y": 0, "width": 74, "height": 40}
    assert "x_mm" not in mark
    assert mark.get("placement") != "provider_defined"


def test_get_mark_without_envelope_omits_placement() -> None:
    mark = _client("deutschepost").envelopes.get_mark("standardbrief", zone_id="domestic")
    assert mark["type"] == "stamp"
    assert mark["size"] == {"width": 37, "height": 20}
    assert "placement" not in mark


def test_get_mark_unknown_envelope_omits_placement() -> None:
    mark = _client("deutschepost").envelopes.get_mark(
        "standardbrief",
        envelope_id="NOT_AN_ENVELOPE",
        zone_id="domestic",
    )
    assert "placement" not in mark
    assert mark.get("placement") != {"x": 0, "y": 0, "width": 0, "height": 0}


def test_laposte_c5_mark_is_label_with_fr_zone() -> None:
    layout = _client("laposte").envelopes.layout(
        "C5",
        "FR",
        "lettre_verte",
        zone_id="domestic",
    )
    assert layout["mark"]["type"] == "label"
    assert layout["mark"]["size"] == {"width": 64, "height": 34}
    assert layout["mark"]["placement"] == {"x": 155, "y": 0, "width": 74, "height": 40}


def test_swisspost_exposes_size_and_placement_even_when_they_disagree() -> None:
    layout = _client("swisspost").envelopes.layout(
        "C5",
        "CH",
        "a_post_standardbrief",
        zone_id="domestic",
    )
    assert layout["mark"]["type"] == "stamp"
    assert layout["mark"]["size"] == {"width": 40, "height": 40}
    assert layout["mark"]["placement"] == {"x": 155, "y": 0, "width": 74, "height": 38}


def test_ukrposhta_ua_dl_window_without_envelope_placement() -> None:
    layout = _client("ukrposhta").envelopes.layout(
        "DL",
        "UA",
        "lyst_standartnyi",
        zone_id="domestic",
    )
    assert layout["window"] == {"x": 110, "y": 45, "width": 90, "height": 45}
    assert layout["mark"]["type"] == "label"
    assert layout["mark"]["size"] == {"width": 148, "height": 210}
    assert "placement" not in layout["mark"]


def test_no_jurisdiction_omits_window() -> None:
    client = _client("deutschepost")
    assert "window" not in client.envelopes.geometry("DL")
    assert "window" not in client.envelopes.layout("C5")
    rows = client.envelopes.list()
    assert all("has_window" not in row for row in rows)
    assert {row["id"] for row in rows} >= {"DL", "C5"}


def test_unknown_jurisdiction_omits_window_keeps_mark() -> None:
    layout = _client("deutschepost").envelopes.layout(
        "C5", "US", "standardbrief", zone_id="domestic"
    )
    assert layout["width"] == 229
    assert "window" not in layout
    assert layout["mark"]["type"] == "stamp"


def test_unknown_envelope_is_not_found() -> None:
    try:
        _client("deutschepost").envelopes.layout("NOT_AN_ENVELOPE")
        raise AssertionError("expected PortoError")
    except PortoError as exc:
        assert exc.code == PortoErrorCode.PORTO_DATA_NOT_FOUND


def test_c5_de_and_ua_windows_differ() -> None:
    client = _client("deutschepost")
    de = client.envelopes.layout("C5", "DE")
    ua = client.envelopes.layout("C5", "UA")
    assert "window" in de
    assert "window" in ua
    assert de["window"] != ua["window"]


def test_same_envelope_de_and_ukrposhta_marks_isolated() -> None:
    de = _client("deutschepost").envelopes.layout("C5", "DE", zone_id="domestic")
    ua = _client("ukrposhta").envelopes.layout("C5", "UA", zone_id="domestic")
    assert de["mark"]["type"] != ua["mark"]["type"] or de["mark"]["size"] != ua["mark"]["size"]


def test_same_envelope_de_and_laposte_marks_isolated() -> None:
    de = _client("deutschepost").envelopes.layout("C5", "DE", zone_id="domestic")
    fr = _client("laposte").envelopes.layout("C5", "FR", zone_id="domestic")
    assert de["mark"]["type"] == "stamp"
    assert fr["mark"]["type"] == "label"


def test_join_without_coupling_ua_window_and_de_placement() -> None:
    layout = _client("deutschepost").envelopes.layout("C5", "UA", zone_id="domestic")
    assert layout["window"] != {"x": 20, "y": 57, "width": 90, "height": 45}
    assert layout["mark"]["placement"] == {"x": 155, "y": 0, "width": 74, "height": 40}
