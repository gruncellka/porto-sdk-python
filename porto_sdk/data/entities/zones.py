"""
Zones Entity Loader

Handles loading and querying zones entity.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import BaseEntityLoader


@dataclass
class PortoZone:
    """
    Zone model - maps to porto-data/schemas/zones.schema.json

    JSON structure:
    {
        "id": "domestic",  # pattern: ^[a-z0-9_]+$
        "name": "Deutschland",
        "description": "Germany",
        "country_codes": ["DE"]  # ISO 3166-1 alpha-2
    }
    Optional catalog fields (e.g. English `label`) are accepted when present.
    """

    id: str
    name: str
    description: str
    country_codes: list[str]
    label: str | None = None


class ZonesLoader(BaseEntityLoader):
    """
    Loads and manages zones entity

    Handles:
    - Loading zones from JSON (supports both dict and list formats)
    - Querying zones by ID or country code
    """

    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._zones: list[PortoZone] = []

    def load(self, data: dict[str, Any]) -> None:
        """
        Transform zones JSON to PortoZone objects

        Supports both dict format (keys are zone IDs) and list format.
        """
        zones_data = data.get("zones", {})
        if isinstance(zones_data, dict):
            self._zones = [
                self._zone_from_row(zone_id, zone_data)
                for zone_id, zone_data in zones_data.items()
                if isinstance(zone_data, dict)
            ]
        else:
            # Fallback for list format
            self._zones = [
                self._zone_from_row(str(z.get("id", "")), z)
                for z in zones_data
                if isinstance(z, dict) and z.get("id")
            ]

    @staticmethod
    def _zone_from_row(zone_id: str, zone_data: dict[str, Any]) -> PortoZone:
        return PortoZone(
            id=zone_id,
            name=str(zone_data.get("name", zone_id)),
            description=str(zone_data.get("description", "")),
            country_codes=list(zone_data.get("country_codes") or []),
            label=zone_data.get("label") if isinstance(zone_data.get("label"), str) else None,
        )

    def get_data(self) -> list[PortoZone]:
        """Get all zones"""
        return self._zones

    # Query methods specific to zones
    def get_zone(self, zone_id: str) -> PortoZone | None:
        """Get zone by ID"""
        return next((z for z in self._zones if z.id == zone_id), None)

    def get_all_zones(self) -> list[PortoZone]:
        """Get all zones"""
        return self._zones

    def get_zone_by_country_code(self, country_code: str) -> PortoZone | None:
        """Get zone by country code"""
        return next((z for z in self._zones if country_code in z.country_codes), None)
