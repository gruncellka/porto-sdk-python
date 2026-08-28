"""Tests for Python SDK registry manifest guard."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_registry.py"
SDK_ROOT = Path(__file__).resolve().parents[1]


def _run_check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def clean_root(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = [\n    "gruncellka-porto-data>=0.7.0",\n]\n',
        encoding="utf-8",
    )
    return tmp_path


def test_passes_clean_pyproject(clean_root: Path) -> None:
    result = _run_check(clean_root)
    assert result.returncode == 0, result.stderr


def test_fails_file_dependency_in_pyproject(clean_root: Path) -> None:
    (clean_root / "pyproject.toml").write_text(
        "[project]\n"
        "dependencies = [\n"
        '    "gruncellka-porto-features @ file:///tmp/porto-features",\n'
        "]\n",
        encoding="utf-8",
    )
    result = _run_check(clean_root)
    assert result.returncode == 1
    assert "local-source" in result.stderr.lower() or "failed" in result.stderr.lower()


def test_sdk_requires_porto_data() -> None:
    result = _run_check(SDK_ROOT)
    assert result.returncode == 0, result.stderr
