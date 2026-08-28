"""Providers registry loader — providers.json"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BaseEntityLoader


@dataclass
class PortoProvider:
    id: str
    name: str
    """Official / legal operator name (connection surfaces)."""
    label: str
    """Short display name (chrome, pickers)."""
    country: str
    mark_types: list[str] = field(default_factory=list)


class ProvidersLoader(BaseEntityLoader):
    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._providers: dict[str, PortoProvider] = {}

    def load(self, data: dict[str, Any]) -> None:
        self._providers = {}
        providers = data.get("providers") or {}
        for provider_id, row in providers.items():
            row = row or {}
            official = str(row.get("name") or provider_id)
            short = str(row.get("label") or official)
            self._providers[provider_id] = PortoProvider(
                id=provider_id,
                name=official,
                label=short,
                country=str(row.get("country", "")),
                mark_types=list(row.get("mark_types") or []),
            )

    def get_data(self) -> dict[str, PortoProvider]:
        return self._providers

    def get_provider(self, provider_id: str) -> PortoProvider | None:
        return self._providers.get(provider_id)

    def list_providers(self) -> list[PortoProvider]:
        return list(self._providers.values())
