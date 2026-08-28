"""Schema enum lock: kinds.schema.json == SDK ServiceKind / FeatureKind literals."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from porto_sdk.kinds import FEATURE_KINDS, SERVICE_KINDS


@pytest.mark.offline
def test_kind_literals_match_schema(porto_data_path: str) -> None:
    schema_path = Path(porto_data_path) / "schemas" / "kinds.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    service = schema["definitions"]["service_kind"]["enum"]
    feature = schema["definitions"]["feature_kind"]["enum"]
    assert set(service) == SERVICE_KINDS
    assert set(feature) == FEATURE_KINDS
    assert list(service) == sorted(SERVICE_KINDS, key=service.index)
    assert list(feature) == sorted(FEATURE_KINDS, key=feature.index)
