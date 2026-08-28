"""Resolution result cache — TTL + LRU for ``PortoResolver.resolve`` only."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ...config import CacheConfig
from ...kinds import ServiceKind
from ...types import Dimensions
from .types import DeliveryPreference


class ResolutionCacheKeyRequest(Protocol):
    country_code: str
    weight: int
    product_id: str | None
    envelope_id: str | None
    dimensions: Dimensions | None
    delivery_preference: DeliveryPreference | None
    indemnity_tier: str | None
    services: list[ServiceKind] | None
    service_ids: list[str] | None


@dataclass(frozen=True)
class _CacheEntry:
    data: object
    timestamp: datetime


def _sorted_csv(values: list[str] | None) -> str:
    if not values:
        return ""
    return ",".join(sorted(str(v) for v in values if v is not None and str(v) != ""))


class ResolutionCache:
    """Caches full ``resolve()`` results. Not a generic application cache."""

    def __init__(self, config: CacheConfig):
        self.config = config
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()

    def generate_key(self, provider_id: str, request: ResolutionCacheKeyRequest) -> str:
        """Key = fields that change a resolution result (order-independent for lists)."""
        product_id = request.product_id or ""
        preference = request.delivery_preference or ""
        indemnity = request.indemnity_tier or ""
        envelope = request.envelope_id or ""
        kinds = _sorted_csv(list(request.services) if request.services else None)
        pins = _sorted_csv(request.service_ids)
        dims = ""
        if request.dimensions is not None:
            dims = (
                f"{request.dimensions.length}x{request.dimensions.width}x"
                f"{request.dimensions.height}"
            )
        return (
            f"resolve:{provider_id}:{request.country_code}:{request.weight}:"
            f"{product_id}:{envelope}:{dims}:{preference}:{indemnity}:{kinds}:{pins}"
        )

    def get(self, key: str) -> object | None:
        if not self.config.enabled:
            return None

        entry = self._cache.get(key)
        if not entry:
            return None

        if datetime.now() - entry.timestamp > self.config.ttl:
            self._cache.pop(key, None)
            return None

        self._cache.move_to_end(key)
        return entry.data

    def set(self, key: str, data: object) -> None:
        if not self.config.enabled:
            return

        if len(self._cache) >= self.config.max_size:
            self._evict_oldest(count=10)

        self._cache[key] = _CacheEntry(data=data, timestamp=datetime.now())
        self._cache.move_to_end(key)

    def clear(self) -> None:
        self._cache.clear()

    def _evict_oldest(self, count: int = 10) -> None:
        for _ in range(min(count, len(self._cache))):
            if self._cache:
                self._cache.popitem(last=False)

    def size(self) -> int:
        return len(self._cache)

    def max_size(self) -> int:
        return self.config.max_size
