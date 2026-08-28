"""Unit tests for ArtifactContract wheel and sdist path rules."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "release" / "verify_artifact.py"


def _load_verify():
    spec = importlib.util.spec_from_file_location("verify_artifact", VERIFY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_contract_accepts_clean_wheel_listing() -> None:
    check = _load_verify().check_wheel
    names = [
        "porto_sdk/__init__.py",
        "porto_sdk/py.typed",
        "gruncellka_porto_sdk-0.1.0.dist-info/METADATA",
        "gruncellka_porto_sdk-0.1.0.dist-info/WHEEL",
        "gruncellka_porto_sdk-0.1.0.dist-info/licenses/LICENSE",
    ]
    assert check(names) == []


def test_contract_rejects_tests_path_in_wheel() -> None:
    check = _load_verify().check_wheel
    names = [
        "porto_sdk/__init__.py",
        "porto_sdk/py.typed",
        "gruncellka_porto_sdk-0.1.0.dist-info/METADATA",
        "gruncellka_porto_sdk-0.1.0.dist-info/WHEEL",
        "tests/test_foo.py",
    ]
    errors = check(names)
    assert errors


def test_contract_accepts_clean_sdist_listing() -> None:
    check = _load_verify().check_sdist
    names = [
        "gruncellka_porto_sdk-0.1.0/porto_sdk/__init__.py",
        "gruncellka_porto_sdk-0.1.0/porto_sdk/py.typed",
        "gruncellka_porto_sdk-0.1.0/pyproject.toml",
        "gruncellka_porto_sdk-0.1.0/README.md",
        "gruncellka_porto_sdk-0.1.0/LICENSE",
        "gruncellka_porto_sdk-0.1.0/CHANGELOG.md",
        "gruncellka_porto_sdk-0.1.0/PKG-INFO",
        "gruncellka_porto_sdk-0.1.0/MANIFEST.in",
        "gruncellka_porto_sdk-0.1.0/gruncellka_porto_sdk.egg-info/PKG-INFO",
    ]
    assert check(names) == []


def test_contract_rejects_tests_in_sdist() -> None:
    check = _load_verify().check_sdist
    names = [
        "gruncellka_porto_sdk-0.1.0/porto_sdk/__init__.py",
        "gruncellka_porto_sdk-0.1.0/pyproject.toml",
        "gruncellka_porto_sdk-0.1.0/README.md",
        "gruncellka_porto_sdk-0.1.0/LICENSE",
        "gruncellka_porto_sdk-0.1.0/CHANGELOG.md",
        "gruncellka_porto_sdk-0.1.0/PKG-INFO",
        "gruncellka_porto_sdk-0.1.0/tests/test_foo.py",
    ]
    errors = check(names)
    assert any("tests" in e for e in errors)
