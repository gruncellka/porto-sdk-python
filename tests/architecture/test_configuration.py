"""Canonical PortoConfig / adapter layout contracts."""

from __future__ import annotations

import ast
from pathlib import Path

_SDK = Path(__file__).resolve().parents[2] / "porto_sdk"


def test_porto_config_has_canonical_fields() -> None:
    source = (_SDK / "config.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fields: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "PortoConfig":
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    fields.add(item.target.id)
    assert "providers" in fields
    assert "data" in fields
    assert "transport" in fields


def test_canonical_time_config_has_no_unit_suffixes() -> None:
    source = (_SDK / "config.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in {"CacheConfig", "TransportConfig"}:
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    name = item.target.id
                    assert not name.endswith("_ms"), name
                    assert not name.endswith("_seconds"), name


def test_status_map_literals_live_under_provider_adapters() -> None:
    tracking = _SDK / "adapters" / "tracking"
    for path in tracking.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "TrackingState.CREATED" not in text, f"map literal leaked into {path.name}"
        assert "STATUS_MAP" not in text or "from .." in text or path.name == "acl.py"


def test_errors_do_not_import_adapters() -> None:
    errors = _SDK / "errors"
    for path in errors.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "porto_sdk.adapters" not in text
        assert "from ..adapters" not in text
        assert "internetmarke" not in text.lower() or path.name == "codes.py"
