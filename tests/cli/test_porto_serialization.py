"""CLI resolve output must mirror canonical Porto serialization."""

from __future__ import annotations

import json
import sys

import pytest

from porto_sdk.cli import main
from porto_sdk.cli._output import serialize_porto
from porto_sdk.client import PortoClient
from porto_sdk.config import PortoConfig, ProviderRuntimeConfig
from tests.support.porto_features_path import get_porto_data_path

PORTO_JSON_KEYS = frozenset(
    {
        "product",
        "zone",
        "weight_tier",
        "amount",
        "currency",
        "components",
        "features",
        "available_services",
        "is_valid",
        "warnings",
        "restrictions",
        "delivery_hint",
        "mark_type",
        "tracking",
        "requires",
        "services",
        "service_ids",
    }
)


def _resolve_porto() -> object:
    client = PortoClient(
        PortoConfig(
            data=get_porto_data_path(),
            providers={"deutschepost": ProviderRuntimeConfig()},
        )
    )
    return client.provider("deutschepost").resolve(country_code="DE", weight=20)


@pytest.mark.offline
def test_serialize_porto_matches_model_dump() -> None:
    porto = _resolve_porto()
    assert set(serialize_porto(porto).keys()) == PORTO_JSON_KEYS
    assert serialize_porto(porto) == porto.model_dump(mode="json")


@pytest.mark.offline
def test_cli_resolve_json_is_canonical_porto(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PORTO_DATA_PATH", get_porto_data_path())
    monkeypatch.setattr(
        sys,
        "argv",
        ["porto", "resolve", "--country", "DE", "--weight", "20", "--provider", "deutschepost", "--json"],
    )
    main()
    cli_payload = json.loads(capsys.readouterr().out)

    assert set(cli_payload.keys()) == PORTO_JSON_KEYS
    assert "price" not in cli_payload
    assert cli_payload == serialize_porto(_resolve_porto())
