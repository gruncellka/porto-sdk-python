"""Ensure generic SDK service layers contain no provider-specific string literals."""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVICES = _REPO / "porto_sdk" / "services"
_RESOLUTION = _SERVICES / "resolution"

_FORBIDDEN = (
    "deutschepost",
    "internetmarke",
    "portokasse",
    "freigabe",
    "deutsche post",
)


def _py_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.py") if p.is_file())


@pytest.mark.parametrize("path", _py_files(_SERVICES) + _py_files(_RESOLUTION))
def test_generic_services_have_no_provider_literals(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    for token in _FORBIDDEN:
        assert token not in text, f"{path.relative_to(_REPO)} must not reference {token!r}"
