"""Delivery hint resolution from products.delivery[] + markets.working_days."""

from dataclasses import dataclass

from ...data.entities.products import DeliveryEntry, DeliverySpan, DeliveryWeekdays, PortoProduct
from ...data.loader import PortoDataLoader
from ...errors.domains.data import raise_data_invalid


def _parse_weekdays_fallback(raw: str) -> DeliveryWeekdays:
    token = str(raw or "").strip()
    if token in ("mon_fri", "mon_sat"):
        return token  # type: ignore[return-value]
    raise_data_invalid(f"Unknown delivery weekdays: {raw!r}", details={"weekdays": raw})
    raise AssertionError("unreachable")


@dataclass
class WorkingDaysHint:
    market: str
    weekdays: DeliveryWeekdays
    exclude_public_holidays: bool


@dataclass
class DeliveryHint:
    span: DeliverySpan
    days_max: int
    days_min: int | None
    working_days: WorkingDaysHint


class DeliveryResolver:
    def __init__(self, loader: PortoDataLoader, provider_id: str):
        self._loader = loader
        self._provider_id = provider_id

    def find_delivery_entry(self, product: PortoProduct, zone_id: str) -> DeliveryEntry | None:
        for entry in product.delivery:
            if zone_id in entry.zones:
                return entry
        return None

    def resolve(self, product: PortoProduct, zone_id: str) -> DeliveryHint | None:
        entry = self.find_delivery_entry(product, zone_id)
        if entry is None:
            return None

        provider = self._loader.get_provider(self._provider_id)
        if provider is None:
            return None
        market = self._loader.get_market(provider.country)
        if market is None:
            return None

        weekdays = entry.weekdays or _parse_weekdays_fallback(market.working_days.weekdays)
        return DeliveryHint(
            span=entry.span,
            days_max=entry.days_max,
            days_min=entry.days_min,
            working_days=WorkingDaysHint(
                market=market.country_code,
                weekdays=weekdays,
                exclude_public_holidays=market.working_days.exclude_public_holidays,
            ),
        )

    def delivery_fingerprint(self, product: PortoProduct, zone_id: str) -> tuple | None:
        entry = self.find_delivery_entry(product, zone_id)
        if entry is None:
            return None
        return (entry.span, entry.days_min, entry.days_max, entry.weekdays)
