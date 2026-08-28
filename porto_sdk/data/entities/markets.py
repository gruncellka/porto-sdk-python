"""Markets entity loader — policy/markets.json"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import BaseEntityLoader


@dataclass
class WorkingDays:
    weekdays: str
    exclude_public_holidays: bool


@dataclass
class PortoMarket:
    country_code: str
    currency: str
    working_days: WorkingDays
    vat: dict[str, Any] | None = None
    international_currency: list | None = None


class MarketsLoader(BaseEntityLoader):
    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._markets: dict[str, PortoMarket] = {}

    def load(self, data: dict[str, Any]) -> None:
        self._markets = {}
        for country_code, row in (data.get("markets") or {}).items():
            wd = (row or {}).get("working_days") or {}
            self._markets[country_code] = PortoMarket(
                country_code=country_code,
                currency=str((row or {}).get("currency", "")),
                working_days=WorkingDays(
                    weekdays=str(wd.get("weekdays", "mon_fri")),
                    exclude_public_holidays=bool(wd.get("exclude_public_holidays", True)),
                ),
                vat=(row or {}).get("vat"),
                international_currency=(row or {}).get("international_currency"),
            )

    def get_data(self) -> dict[str, PortoMarket]:
        return self._markets

    def get_market(self, country_code: str) -> PortoMarket | None:
        return self._markets.get(country_code.upper())
