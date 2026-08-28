"""client.provider(id) binds catalog ids without an empty config row."""

from __future__ import annotations

import pytest

from porto_sdk import PortoClient, PortoConfig
from porto_sdk.config import ProviderRuntimeConfig
from porto_sdk.errors import PortoError, PortoErrorCode


@pytest.mark.offline
def test_omitted_providers_binds_catalog_ids(porto_data_path) -> None:
    client = PortoClient(PortoConfig(data=porto_data_path))
    assert client.provider("deutschepost").provider_id == "deutschepost"
    assert client.provider("swisspost").provider_id == "swisspost"


@pytest.mark.offline
def test_constructor_without_config_binds_catalog_ids(porto_data_path, monkeypatch) -> None:
    from porto_sdk.data import porto_data_registry as registry

    monkeypatch.setattr(registry, "find_porto_data_path", lambda: porto_data_path)
    client = PortoClient()
    assert client.provider("deutschepost").provider_id == "deutschepost"


@pytest.mark.offline
def test_unknown_provider_id_fails(porto_data_path) -> None:
    client = PortoClient(PortoConfig(data=porto_data_path))
    with pytest.raises(PortoError) as exc:
        client.provider("not-a-carrier")
    assert exc.value.code == PortoErrorCode.PORTO_PROVIDER_NOT_CONFIGURED


@pytest.mark.offline
def test_present_allowlist_forbids_unlisted(porto_data_path) -> None:
    client = PortoClient(
        PortoConfig(
            data=porto_data_path,
            providers={"deutschepost": ProviderRuntimeConfig()},
        )
    )
    with pytest.raises(PortoError) as exc:
        client.provider("laposte")
    assert exc.value.code == PortoErrorCode.PORTO_PROVIDER_NOT_CONFIGURED
    client.provider("deutschepost")
