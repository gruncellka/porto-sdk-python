"""
Products Entity Loader
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ...execution import MarkType, TrackingMode, parse_mark_type, parse_tracking_mode
from ...requires import Requirement, parse_requires_list
from .base import BaseEntityLoader

DeliverySpan = Literal["next", "within", "between"]
DeliveryWeekdays = Literal["mon_fri", "mon_sat"]


@dataclass
class DeliveryEntry:
    zones: list[str]
    span: DeliverySpan
    days_max: int
    days_min: int | None = None
    weekdays: DeliveryWeekdays | None = None


@dataclass
class ProductIndemnity:
    tier: str
    max_amount: int


@dataclass
class PortoProduct:
    """Product model — maps to porto-data/schemas/products.schema.json"""

    id: str
    name: str
    envelope_ids: list[str] = field(default_factory=list)
    zones: list[str] = field(default_factory=list)
    weight_tier: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    provider_mappings: dict[str, dict[str, Any]] | None = None
    mark_type: MarkType | None = None
    tracking: TrackingMode | None = None
    label: str | None = None
    delivery: list[DeliveryEntry] = field(default_factory=list)
    included_features: list[str] = field(default_factory=list)
    indemnity: ProductIndemnity | None = None
    requires: tuple[Requirement, ...] = ()


def _parse_span(raw: object) -> DeliverySpan:
    token = str(raw or "").strip()
    if token in ("next", "within", "between"):
        return token  # type: ignore[return-value]
    from ...errors.domains.data import raise_data_invalid

    raise_data_invalid(f"Unknown delivery span: {raw!r}", details={"span": raw})
    raise AssertionError("unreachable")


def _parse_weekdays(raw: object) -> DeliveryWeekdays | None:
    if raw is None or raw == "":
        return None
    token = str(raw).strip()
    if token in ("mon_fri", "mon_sat"):
        return token  # type: ignore[return-value]
    from ...errors.domains.data import raise_data_invalid

    raise_data_invalid(f"Unknown delivery weekdays: {raw!r}", details={"weekdays": raw})
    raise AssertionError("unreachable")


def _parse_delivery(raw: Any) -> list[DeliveryEntry]:
    if not isinstance(raw, list):
        return []
    entries: list[DeliveryEntry] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        entries.append(
            DeliveryEntry(
                zones=list(row.get("zones") or []),
                span=_parse_span(row.get("span")),
                days_max=int(row.get("days_max", 0)),
                days_min=row.get("days_min"),
                weekdays=_parse_weekdays(row.get("weekdays")),
            )
        )
    return entries


def _parse_indemnity(raw: Any) -> ProductIndemnity | None:
    if not isinstance(raw, dict):
        return None
    tier = raw.get("tier")
    max_row = raw.get("max") or {}
    amount = max_row.get("amount") if isinstance(max_row, dict) else None
    if not tier or amount is None:
        return None
    return ProductIndemnity(tier=str(tier), max_amount=int(amount))


class ProductsLoader(BaseEntityLoader):
    """Loads and manages products entity."""

    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._products: list[PortoProduct] = []

    def load(self, data: dict[str, Any]) -> None:
        products_data = data.get("products", [])
        self._products = []
        for p in products_data:
            envelope_ids = p.get("envelope_ids") or []
            zones = p.get("zones") or []
            self._products.append(
                PortoProduct(
                    id=p["id"],
                    name=p["name"],
                    envelope_ids=list(envelope_ids),
                    zones=list(zones),
                    weight_tier=p.get("weight_tier"),
                    effective_from=p.get("effective_from"),
                    effective_to=p.get("effective_to"),
                    provider_mappings=p.get("provider_mappings"),
                    mark_type=parse_mark_type(p.get("mark_type"), allow_none=True),
                    tracking=parse_tracking_mode(p.get("tracking"), allow_none=True),
                    label=p.get("label") if isinstance(p.get("label"), str) else None,
                    delivery=_parse_delivery(p.get("delivery")),
                    included_features=list(p.get("included_features") or []),
                    indemnity=_parse_indemnity(p.get("indemnity")),
                    requires=parse_requires_list(p.get("requires"), path="products.requires"),
                )
            )

    def get_data(self) -> list[PortoProduct]:
        return self._products

    def get_product(self, product_id: str) -> PortoProduct | None:
        return next((p for p in self._products if p.id == product_id), None)

    def get_all_products(self) -> list[PortoProduct]:
        return self._products
