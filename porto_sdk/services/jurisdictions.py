"""Jurisdiction reference lookups (timezone, membership blocs, country codes)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..errors.domains.resolution import raise_destination_invalid

if TYPE_CHECKING:
    from ..data.loader import PortoDataLoader

_DEFAULT_TIMEZONE = "UTC"


class JurisdictionsService:
    """Typed read surface over porto-data ``policy/jurisdictions.json``."""

    def __init__(self, data_loader: PortoDataLoader):
        self._loader = data_loader

    def timezone_for_country(self, country_code: str) -> str:
        """IANA timezone for an ISO 3166-1 alpha-2 country (fallback ``UTC``)."""
        code = (country_code or "").strip().upper()
        if not code:
            return _DEFAULT_TIMEZONE
        return self._loader.get_timezone_for_country(code) or _DEFAULT_TIMEZONE

    def timezone_by_country(self) -> dict[str, str]:
        """Map of uppercase country codes → IANA timezone ids."""
        return self._loader.get_timezone_by_country()

    def country_codes(self) -> list[str]:
        """Sorted ISO 3166-1 alpha-2 keys known to jurisdictions (excludes EU/UN)."""
        return self._loader.country_codes()

    def country_code_3(self, country_code: str) -> str:
        """ISO 3166-1 alpha-3 for an alpha-2 country (one-way; no reverse lookup)."""
        code = (country_code or "").strip().upper()
        value = self._loader.get_country_code_3(code) if code else None
        if not value:
            raise_destination_invalid(
                f"Unknown country code: {country_code}",
                country_code=code or str(country_code or ""),
                status_code=400,
            )
        return value
