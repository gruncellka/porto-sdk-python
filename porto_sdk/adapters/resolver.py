"""
Adapter resolver — maps provider id to adapter instances.
No business logic. Adding a new provider = add adapter + register here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..config import WireConfig
from .datafactory import DataFactoryAdapter, OfflineDataFactoryAdapter
from .execution_registry import get_execution_adapter, get_tracking_adapter

if TYPE_CHECKING:
    from ..client import PortoClient


def get_address_adapter(
    provider_id: str,
    wires: dict[str, WireConfig] | None,
    client: PortoClient | None = None,
    http_client=None,
) -> DataFactoryAdapter | OfflineDataFactoryAdapter:
    """Resolve address adapter for a provider."""
    provider = provider_id.strip().lower()
    if provider == "deutschepost":
        df = (wires or {}).get("datafactory")
        if df and df.credentials:
            cid = df.credentials.get("client_id")
            csec = df.credentials.get("client_secret")
            if cid and csec:
                return DataFactoryAdapter(
                    client_id=cid,
                    client_secret=csec,
                    base_url=df.base_url or "https://api-eu.dhl.com/datafactory/autocomplete",
                    client=client,
                    http_client=http_client,
                )
    return OfflineDataFactoryAdapter()


__all__ = [
    "get_address_adapter",
    "get_execution_adapter",
    "get_tracking_adapter",
]
