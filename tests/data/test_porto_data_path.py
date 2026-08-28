"""Tests for porto-data path resolution in test helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tests.support import porto_features_path as paths


def test_get_porto_data_path_prefers_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_root = tmp_path / "env-data"
    env_root.mkdir()
    (env_root / "mappings.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PORTO_DATA_PATH", str(env_root))

    with patch(
        "porto_sdk.data.porto_data_registry.find_porto_data_path",
        side_effect=ValueError("no pip"),
    ):
        assert paths.get_porto_data_path() == str(env_root.resolve())


def test_get_porto_data_path_uses_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PORTO_DATA_PATH", raising=False)
    pip_path = str(tmp_path / "pip-data")

    with patch(
        "porto_sdk.data.porto_data_registry.find_porto_data_path",
        return_value=pip_path,
    ):
        assert paths.get_porto_data_path() == pip_path


def test_get_porto_data_path_raises_when_env_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "not-a-catalog"
    missing.mkdir()
    monkeypatch.setenv("PORTO_DATA_PATH", str(missing))

    with pytest.raises(FileNotFoundError, match="PORTO_DATA_PATH"):
        paths.get_porto_data_path()


def test_get_porto_data_path_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PORTO_DATA_PATH", raising=False)

    with patch(
        "porto_sdk.data.porto_data_registry.find_porto_data_path",
        side_effect=ValueError("no pip"),
    ):
        with pytest.raises(FileNotFoundError, match="gruncellka-porto-data"):
            paths.get_porto_data_path()
