"""Test-only helper — not a public PortoClient shim."""

from porto_sdk import PortoClient
from porto_sdk.provider_client import ProviderClient


def bound_provider(client: PortoClient, provider_id: str = "deutschepost") -> ProviderClient:
    return client.provider(provider_id)
