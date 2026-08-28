"""
Zone Resolver - Resolves zone from country code.

Resolution primitive: country_code -> PortoZone via validator + loader.
"""

from typing import Any

from ...data.domain_validator import DomainIds


class ZoneResolver:
    """Resolves zone from country code."""

    def __init__(self, validator: DomainIds):
        self._validator = validator

    def resolve(self, country_code: str) -> dict[str, Any]:
        """
        Resolve zone from country code.
        Returns dict with is_valid, data (zone), or errors.
        """
        result = self._validator.validate_country_code(country_code)
        if not result.is_valid or result.data is None:
            return {"is_valid": False, "errors": result.errors or ["No zone data"]}
        zone_data = result.data["zone"]
        return {"is_valid": True, "data": {"zone": zone_data}}
