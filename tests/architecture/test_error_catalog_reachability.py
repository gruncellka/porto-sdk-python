"""Catalog codes must be emitted somewhere; undeclared error-like PORTO_* strings fail."""

from __future__ import annotations

import re
from pathlib import Path

from porto_sdk.errors import PortoErrorCode

_REPO = Path(__file__).resolve().parents[2]
_SDK = _REPO / "porto_sdk"

# Env / config tokens that are not error codes.
_NON_ERROR_LITERALS = frozenset(
    {
        "PORTO_DATA_PATH",
        "PORTO_FEATURES_PATH",
        "PORTO_TIMEOUT",
        "PORTO_PROVIDER",
        "PORTO_RETRIES",
        "PORTO_DATA_VERSION_MIN",
        "PORTO_DATA_VERSION_MAX_EXCLUSIVE",
        "PORTO_DATA_MAPPING",
        "PORTO_DATA_CATALOG_UNRESOLVED",
    }
)

_LITERAL = re.compile(r'"(PORTO_[A-Z0-9_]+)"')
_ERRORISH = re.compile(
    r"^PORTO_(?:[A-Z0-9]+_)+(?:FAILED|DENIED|PENDING|INSUFFICIENT|HEAVY|INVALID|FOUND|"
    r"AMBIGUOUS|TIMEOUT|LIMITED|UNAVAILABLE|CORRUPTED|OLD|NEW|UNSUPPORTED|CONFIGURED|"
    r"INCOMPATIBLE)$"
)


def _iter_sdk_py() -> list[Path]:
    return sorted(
        p
        for p in _SDK.rglob("*.py")
        if p.is_file() and p.name != "codes.py" and "__pycache__" not in p.parts
    )


def _blob() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in _iter_sdk_py())


def test_every_error_code_is_referenced_outside_generated_enum() -> None:
    blob = _blob()
    missing = [code.value for code in PortoErrorCode if code.value not in blob]
    assert missing == [], f"catalog codes never referenced in porto_sdk/: {missing}"


def test_no_undeclared_error_like_porto_string_literals() -> None:
    catalog = {code.value for code in PortoErrorCode}
    undeclared: list[str] = []
    for path in _iter_sdk_py():
        text = path.read_text(encoding="utf-8")
        for match in _LITERAL.finditer(text):
            token = match.group(1)
            if token in catalog or token in _NON_ERROR_LITERALS:
                continue
            if _ERRORISH.match(token):
                undeclared.append(f"{path.relative_to(_REPO)}:{token}")
    assert undeclared == [], f"undeclared error-like PORTO_* literals: {undeclared}"
