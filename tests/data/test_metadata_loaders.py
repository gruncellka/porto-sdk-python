"""Unit tests for metadata entity loaders and envelope matching."""

from pathlib import Path

import pytest

from porto_sdk.data.loader import PortoDataLoader
from porto_sdk.envelopes.match import EnvelopeMatchService, JsonFormatCatalog


@pytest.fixture(scope="module")
def data_path() -> str:
    root = Path(__file__).resolve().parents[3]
    candidate = root / "resources" / "porto-data" / "porto_data"
    if candidate.is_dir():
        return str(candidate)
    pytest.skip("porto-data submodule not available")


@pytest.fixture(scope="module")
def loader(data_path: str) -> PortoDataLoader:
    return PortoDataLoader(data_path, provider="deutschepost")


def test_list_providers(loader: PortoDataLoader) -> None:
    providers = loader.list_providers()
    assert any(p.id == "deutschepost" for p in providers)


def test_list_envelopes_includes_dl(loader: PortoDataLoader) -> None:
    envelopes = loader.list_envelopes()
    ids = {e.id for e in envelopes}
    assert "DL" in ids
    assert "C4" in ids


def test_dl_geometry(loader: PortoDataLoader) -> None:
    envelope = loader.get_envelope("DL")
    assert envelope is not None
    assert envelope.width == 220
    assert envelope.height == 110


def test_products_use_envelope_ids(loader: PortoDataLoader) -> None:
    product = loader.get_product("standardbrief")
    assert product is not None
    assert "DL" in product.envelope_ids


def test_strict_match_dl_standardbrief(loader: PortoDataLoader) -> None:
    product = loader.get_product("standardbrief")
    assert product is not None
    match = EnvelopeMatchService(JsonFormatCatalog(loader._envelopes_loader)).resolve_by_id(
        "DL", product
    )
    assert match.kind == "strict_match"


def test_advisory_match_c4_standardbrief(loader: PortoDataLoader) -> None:
    product = loader.get_product("standardbrief")
    assert product is not None
    match = EnvelopeMatchService(JsonFormatCatalog(loader._envelopes_loader)).resolve_by_id(
        "C4", product
    )
    assert match.kind == "advisory_match"
    assert match.advisory_only is True
    assert match.reason == "regional_format"
