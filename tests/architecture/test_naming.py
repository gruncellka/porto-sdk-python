"""Compile-time identifier and duration fixtures."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from porto_sdk.ids import ProviderId, WireId
from porto_sdk.states import CapabilityState

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "id_swap.py"


def test_provider_id_is_not_wire_id() -> None:
    assert ProviderId is not WireId
    assert ProviderId.__name__ == "ProviderId"
    assert WireId.__name__ == "WireId"


def test_capability_state_is_not_boolean_collapse() -> None:
    assert CapabilityState.ABSENT != CapabilityState.UNSUPPORTED
    assert CapabilityState.UNAVAILABLE != CapabilityState.FAILED
    assert bool(CapabilityState.READY) is True
    assert bool(CapabilityState.ABSENT) is False
    assert bool(CapabilityState.UNSUPPORTED) is False


def test_mypy_rejects_provider_id_as_wire_id() -> None:
    if shutil.which("mypy") is None:
        pytest.skip("mypy is not installed")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--no-error-summary",
            "--pretty",
            str(_FIXTURE),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, result.stdout + result.stderr
    combined = f"{result.stdout}\n{result.stderr}".lower()
    assert "wireid" in combined or "incompatible" in combined
