import json
import sys
from pathlib import Path

import pytest

from porto_sdk.cli import main
from porto_sdk.config import PortoConfig


@pytest.mark.offline
def test_constructor_config_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORTO_TIMEOUT", "12")
    config = PortoConfig(data="/tmp/explicit")
    assert config.data == "/tmp/explicit"


@pytest.mark.offline
def test_from_env_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORTO_TIMEOUT", "31")
    monkeypatch.setenv("PORTO_RETRIES", "2")
    config = PortoConfig.from_env()
    assert config.data is None
    assert config.resolved_transport().timeout.total_seconds() == 31
    assert config.resolved_transport().retries == 2


@pytest.mark.offline
def test_cli_config_check_json_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    data_path = tmp_path / "porto_data"
    data_path.mkdir()
    (data_path / "mappings.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PORTO_DATA_PATH", str(data_path))
    monkeypatch.setattr(sys, "argv", ["porto", "config", "check", "--json"])
    main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["data"] == str(data_path)
