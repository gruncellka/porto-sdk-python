"""Public-surface architecture: core must stay provider-neutral; SDK must not mention Lab."""

from __future__ import annotations

import re
from pathlib import Path

_SDK = Path(__file__).resolve().parents[2] / "porto_sdk"

_LAB_TOKENS = ("PORTO_LAB_", "lab_http", "lab_status", "lab-http")
_LAB_WORD = re.compile(r"\blab\b", re.IGNORECASE)
_PROVIDER_TOKENS = ("internetmarke", "portokasse", "dhl_")
_CORE_FILES = (
    "client.py",
    "mark_content.py",
    "execution.py",
    "types.py",
    "config.py",
    "provider_client.py",
    "__init__.py",
)
_CORE_DIRS = ("errors", "services", "transport")


def _py_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def test_sdk_package_has_no_lab_vocabulary() -> None:
    for path in _py_files(_SDK):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(_SDK)
        for token in _LAB_TOKENS:
            assert token not in text, f"{rel} must not contain {token!r}"
        match = _LAB_WORD.search(text)
        assert match is None, f"{rel} must not contain word {match.group(0)!r}"


def test_core_has_no_provider_acl() -> None:
    files = [_SDK / name for name in _CORE_FILES if (_SDK / name).is_file()]
    for directory in _CORE_DIRS:
        files.extend(_py_files(_SDK / directory))
    for path in files:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(_SDK)
        assert "adapters.deutschepost" not in text, f"{rel} imports deutschepost adapter"
        lower = text.lower()
        for token in _PROVIDER_TOKENS:
            assert token not in lower, f"{rel} must not contain {token!r}"
