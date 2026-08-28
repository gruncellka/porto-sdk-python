"""Unit tests for ArtifactContract wheel path rules."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "release" / "verify_artifact.py"


def _load_check_wheel():
    spec = importlib.util.spec_from_file_location("verify_artifact", VERIFY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.check_wheel


def test_contract_accepts_clean_wheel_listing() -> None:
    check = _load_check_wheel()
    names = [
        "porto_sdk/__init__.py",
        "porto_sdk/py.typed",
        "gruncellka_porto_sdk-0.1.0.dist-info/METADATA",
        "gruncellka_porto_sdk-0.1.0.dist-info/WHEEL",
    ]
    assert check(names) == []


def test_contract_rejects_tests_path() -> None:
    check = _load_check_wheel()
    names = [
        "porto_sdk/__init__.py",
        "gruncellka_porto_sdk-0.1.0.dist-info/METADATA",
        "gruncellka_porto_sdk-0.1.0.dist-info/WHEEL",
        "tests/test_foo.py",
    ]
    errors = check(names)
    assert errors
