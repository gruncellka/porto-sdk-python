"""Exact equality: porto-features errors.json codes == PortoErrorCode values."""

from __future__ import annotations

import json

from porto_sdk.errors import PortoErrorCode
from tests.support.porto_features_path import get_porto_features_root


def test_error_catalog_exact_match_enum() -> None:
    path = get_porto_features_root() / "errors.json"
    assert path.is_file(), f"missing catalog: {path}"
    doc = json.loads(path.read_text(encoding="utf-8"))
    catalog = [str(row["code"]) for row in doc.get("codes") or []]
    enum_values = [item.value for item in PortoErrorCode]
    assert enum_values == catalog, (
        f"PortoErrorCode drift vs errors.json\n"
        f"  missing={sorted(set(catalog) - set(enum_values))}\n"
        f"  extra={sorted(set(enum_values) - set(catalog))}\n"
        f"  order_mismatch={enum_values != catalog}"
    )
