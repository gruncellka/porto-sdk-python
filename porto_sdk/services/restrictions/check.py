"""Compose legal + routing strategies into a public Restrictions result."""

from __future__ import annotations

from datetime import UTC, date, datetime

from ...data.loader import PortoDataLoader
from . import impact as impact_mod
from . import legal as legal_mod
from . import routing as routing_mod
from .types import Restrictions


def for_destination(
    loader: PortoDataLoader,
    country_code: str,
    region_code: str | None = None,
    *,
    provider_id: str | None = None,
    as_of: date | None = None,
) -> Restrictions:
    """Resolve restrictions for one destination under provider origin."""
    today = as_of or datetime.now(UTC).date()
    jurisdictions = loader.provider_jurisdiction_tokens(provider_id)
    catalog = loader.restrictions_catalog()
    legal = legal_mod.resolve(
        catalog["legal"],
        country_code,
        region_code,
        jurisdictions=jurisdictions,
        today=today,
    )
    routing = routing_mod.resolve(catalog["routing"], country_code, region_code)
    return Restrictions(
        impact=impact_mod.resolve(legal, routing, region_precise=bool(region_code)),
        legal=tuple(legal),
        routing=tuple(routing),
    )


class RestrictionsService:
    """Thin façade over porto-data restrictions for ``client.restrictions``."""

    def __init__(self, data_loader: PortoDataLoader, provider_id: str | None = None):
        self._loader = data_loader
        self._provider_id = provider_id or data_loader.provider_id

    def check(
        self,
        country_code: str,
        region_code: str | None = None,
    ) -> Restrictions:
        return for_destination(
            self._loader,
            country_code,
            region_code,
            provider_id=self._provider_id,
        )
