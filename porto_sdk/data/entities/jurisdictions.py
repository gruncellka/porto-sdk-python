"""Jurisdiction reference data (EU/UN blocs, per-country timezones)."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BaseEntityLoader


@dataclass
class PortoJurisdictions:
    jurisdictions: dict[str, Any] = field(default_factory=dict)


class JurisdictionsLoader(BaseEntityLoader):
    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._jurisdictions = PortoJurisdictions()

    def load(self, data: dict[str, Any]) -> None:
        self._jurisdictions = PortoJurisdictions(
            jurisdictions=dict(data.get("jurisdictions") or {}),
        )

    def get_data(self) -> PortoJurisdictions:
        return self._jurisdictions

    def get_jurisdiction(self, key: str) -> dict[str, Any] | None:
        row = self._jurisdictions.jurisdictions.get(key)
        return row if isinstance(row, dict) else None

    def eu_members(self) -> set[str]:
        row = self.get_jurisdiction("EU") or {}
        members = row.get("members") or []
        return {str(item).upper() for item in members if isinstance(item, str)}

    def get_timezone_for_country(self, country_code: str) -> str | None:
        """IANA timezone for a country key; ignores symbolic blocs without country form."""
        code = (country_code or "").strip().upper()
        if not code or code in {"EU", "UN"}:
            return None
        row = self.get_jurisdiction(code)
        if not isinstance(row, dict):
            return None
        tz = row.get("timezone")
        return str(tz) if tz else None

    def get_timezone_by_country(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for key, entry in self._jurisdictions.jurisdictions.items():
            code = str(key).upper()
            if code in {"EU", "UN"} or not isinstance(entry, dict):
                continue
            tz = entry.get("timezone")
            if tz:
                mapping[code] = str(tz)
        return mapping

    def country_codes(self) -> list[str]:
        """Sorted ISO 3166-1 alpha-2 country keys (excludes EU/UN blocs)."""
        codes: list[str] = []
        for key, entry in self._jurisdictions.jurisdictions.items():
            code = str(key).upper()
            if code in {"EU", "UN"} or not isinstance(entry, dict):
                continue
            codes.append(code)
        return sorted(codes)

    def get_country_code_3(self, country_code: str) -> str | None:
        """ISO 3166-1 alpha-3 for an alpha-2 country key (one-way)."""
        code = (country_code or "").strip().upper()
        if not code or code in {"EU", "UN"}:
            return None
        row = self.get_jurisdiction(code)
        if not isinstance(row, dict):
            return None
        value = row.get("country_code_3")
        if isinstance(value, str) and len(value) == 3:
            return value.upper()
        return None
