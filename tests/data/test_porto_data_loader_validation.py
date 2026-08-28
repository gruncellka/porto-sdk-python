# pyright: reportMissingImports=false
from pathlib import Path

import pytest  # type: ignore[import-not-found]

from porto_sdk.data.porto_data_loader import ValidatedPortoDataLoader
from porto_sdk.data.porto_data_validator import PortoDataValidator


@pytest.mark.offline
def test_validated_loader_loads_mapped_files(porto_data_path) -> None:
    data_path = Path(porto_data_path)
    loader = ValidatedPortoDataLoader(data_path, verify_checksums=True)
    loaded = loader.load()
    assert "products.json" in loaded["files"]
    assert loaded["registries"].products
    assert loaded["registries"].resolution_graph.file_type in {"graph", "resolution_graph"}


@pytest.mark.offline
def test_cross_file_validation_detects_broken_reference(porto_data_path) -> None:
    data_path = Path(porto_data_path)
    loader = ValidatedPortoDataLoader(data_path, verify_checksums=True)
    loaded = loader.load()
    validator = PortoDataValidator(
        data_path=data_path,
        metadata=loaded["metadata"],
        mappings=loaded["mappings"],
        verify_checksums=True,
    )
    broken = loaded["registries"]
    broken.products[0].weight_tier = "MISSING_TIER"
    with pytest.raises(Exception):
        validator.validate_cross_file_consistency(broken)
