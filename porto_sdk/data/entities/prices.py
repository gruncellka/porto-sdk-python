"""
Prices Entity Loader

Handles loading and querying prices entity.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import BaseEntityLoader


@dataclass
class PortoPricing:
    """
    Pricing model - maps to porto-data/schemas/prices.schema.json product_prices
    """

    product_id: str
    zone: str
    weight_tier: str
    price: int  # cents - current active price
    currency: str | None = None  # ISO 4217; None → provider graph default
    effective_from: str | None = None
    effective_to: str | None = None


class PricesLoader(BaseEntityLoader):
    """
    Loads and manages prices entity

    Handles:
    - Loading prices from JSON (nested structure with price array)
    - Extracting current active price (first entry in price array)
    - Querying prices by product_id, zone, and weight_tier
    """

    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._prices: list[PortoPricing] = []
        self._service_prices: dict[tuple[str, str | None], int] = {}
        self._zoned_service_ids: set[str] = set()

    def load(self, data: dict[str, Any]) -> None:
        """
        Transform prices JSON to PortoPricing objects

        Extracts current active price from price array (first entry).
        Currency: row override → file unit → None (caller uses provider default).
        """
        product_prices_data = data.get("prices", {}).get("product_prices", [])
        if not product_prices_data:
            product_prices_data = data.get("product_prices", [])
        unit = data.get("unit") or data.get("prices", {}).get("unit") or {}
        file_currency = None
        if isinstance(unit, dict) and unit.get("currency"):
            file_currency = str(unit["currency"]).strip().upper() or None
        self._prices = []

        for pp in product_prices_data:
            price_entries = pp.get("price", [])
            current_price = price_entries[0] if price_entries else {"amount": 0}
            price_amount = current_price.get("amount", current_price.get("price", 0))
            effective_from = current_price.get("effective_from")
            effective_to = current_price.get("effective_to")
            row_currency = pp.get("currency")
            currency = str(row_currency).strip().upper() if row_currency else file_currency

            self._prices.append(
                PortoPricing(
                    product_id=pp["product_id"],
                    zone=pp["zone"],
                    weight_tier=pp["weight_tier"],
                    price=int(price_amount),
                    currency=currency,
                    effective_from=str(effective_from) if effective_from is not None else None,
                    effective_to=str(effective_to) if effective_to is not None else None,
                )
            )

        # Load service_prices keyed by catalog service id and optional zone
        service_prices_data = data.get("prices", {}).get("service_prices", [])
        self._service_prices = {}
        self._zoned_service_ids = set()
        for sp in service_prices_data:
            self._ingest_service_price_row(sp)

    def get_data(self) -> list[PortoPricing]:
        """Get all prices"""
        return self._prices

    # Query methods specific to prices
    def get_pricing(self, product_id: str, zone_id: str, weight_tier: str) -> PortoPricing | None:
        """
        Get pricing for product, zone, and weight_tier combination

        Returns the current active price.
        """
        return next(
            (
                p
                for p in self._prices
                if p.product_id == product_id and p.zone == zone_id and p.weight_tier == weight_tier
            ),
            None,
        )

    def get_prices_for_product(self, product_id: str) -> list[PortoPricing]:
        """Get all prices for a product"""
        return [p for p in self._prices if p.product_id == product_id]

    def get_prices_for_zone(self, zone_id: str) -> list[PortoPricing]:
        """Get all prices for a zone"""
        return [p for p in self._prices if p.zone == zone_id]

    def get_service_price(self, service_id: str, zone_id: str | None = None) -> int | None:
        """
        Get price for a service by catalog id.

        Zoned rows require zone_id. Unzoned rows apply regardless of zone.
        Returns amount in cents, or None if not found.
        """
        if service_id in self._zoned_service_ids:
            if not zone_id:
                return None
            return self._service_prices.get((service_id, zone_id))
        return self._service_prices.get((service_id, None))

    def load_service_prices(self, data: dict[str, Any]) -> None:
        """Load top-level service_prices file (file_type: service_prices)."""
        for sp in data.get("service_prices", []):
            self._ingest_service_price_row(sp)

    def _ingest_service_price_row(self, sp: dict[str, Any]) -> None:
        service_id = sp.get("service_id")
        price_entries = sp.get("price", [])
        if not service_id or not price_entries:
            return
        amount = price_entries[0].get("amount", price_entries[0].get("price", 0))
        zone = sp.get("zone")
        zone_key = str(zone) if zone else None
        self._service_prices[(str(service_id), zone_key)] = int(amount)
        if zone_key is not None:
            self._zoned_service_ids.add(str(service_id))
