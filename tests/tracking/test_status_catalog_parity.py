"""statuses.json set-parity with PortoStatus. Order is not a contract."""

from __future__ import annotations

import json

import pytest

from porto_sdk.types import PortoStatus, TrackingState
from tests.support.porto_features_path import get_porto_features_root


def test_porto_status_values_are_stable() -> None:
    codes = {item.value for item in PortoStatus}
    assert codes == {
        "created",
        "transit",
        "delivery",
        "delivered",
        "returned",
        "undeliverable",
    }
    assert all("_" not in code for code in codes)
    assert TrackingState is PortoStatus


def test_status_catalog_set_parity() -> None:
    path = get_porto_features_root() / "statuses.json"
    if not path.is_file():
        pytest.skip(f"statuses.json not in installed porto-features yet: {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    codes = [str(row["code"]) for row in doc["codes"]]
    assert len(codes) == len(set(codes))
    assert set(codes) == {item.value for item in PortoStatus}
    for row in doc["codes"]:
        assert str(row["description"]).strip()
        assert str(row["domain"]).strip()
