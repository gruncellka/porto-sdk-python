"""
PortoResolver — single data-driven pipeline for all providers.

ONE resolver architecture. No provider branching. All differences come from data.
Orchestration: restriction → zone → weight_tier → product → price → enrich.
"""

from typing import Any, NoReturn

from pydantic import BaseModel, Field

from ..config import CacheConfig
from ..data.context import PostalResolutionContext
from ..data.domain_validator import DomainIds
from ..data.entities.features import Feature
from ..data.entities.services import Service
from ..data.loader import PortoPricing, PortoProduct, PortoWeightTier, PortoZone
from ..errors import PortoError, PortoErrorCode
from ..errors.domains.data import raise_data_not_found
from ..errors.domains.resolution import (
    raise_destination_invalid,
    raise_price_not_found,
    raise_product_not_found,
    raise_too_heavy,
)
from ..execution import MarkType, TrackingMode
from ..kinds import ServiceKind
from ..requires import Requirement
from ..requires import merge as merge_requires
from ..types import Dimensions
from .mark_resolution import resolve_mark_profile_id
from .product_option_types import ServiceOption
from .resolution import (
    DeliveryHint,
    DeliveryPreference,
    DeliveryResolver,
    DestinationCountry,
    FeatureResolver,
    ProductResolver,
    ResolutionCache,
    ServiceResolver,
    WeightTierResolver,
    ZoneResolver,
    validate_service_selection,
)
from .resolution.catalog import PortoCatalog
from .resolution.quote import PriceComponent, compose_quote
from .restrictions import Restrictions, for_destination


class ResolutionRequest(BaseModel):
    """Request for unified resolution"""

    country_code: str
    weight: int
    product_id: str | None = None
    envelope_id: str | None = None
    dimensions: Dimensions | None = None
    delivery_preference: DeliveryPreference | None = None
    indemnity_tier: str | None = None
    services: list[ServiceKind] | None = None
    service_ids: list[str] | None = None


class Porto(BaseModel):
    """Canonical resolved postal intent — catalog product, zone, tier, quote."""

    product: PortoProduct
    zone: PortoZone
    weight_tier: PortoWeightTier
    amount: int
    currency: str = "EUR"
    components: list[PriceComponent] = Field(default_factory=list)
    features: list[Feature] = []
    available_services: list[Service] = []
    is_valid: bool = True
    warnings: list[str] = []
    restrictions: Restrictions = Field(default_factory=lambda: Restrictions(impact=None))
    delivery_hint: DeliveryHint | None = None
    mark_type: MarkType | None = None
    tracking: TrackingMode | None = None
    requires: tuple[Requirement, ...] = ()
    services: tuple[ServiceKind, ...] = ()
    service_ids: tuple[str, ...] = ()

    model_config = {"arbitrary_types_allowed": True}

class PortoResolver:
    """
    PortoResolver — which Porto applies?

    ONE pipeline for all providers: restriction → zone → weight_tier → product → price → enrich.
    Does not own format Match (EnvelopeResolver) or wire/mark binding (ExecutionBinding).
    """

    def __init__(
        self,
        context: PostalResolutionContext,
        validator: DomainIds,
        cache_config: CacheConfig | None = None,
    ):
        self.context = context
        self.validator = validator
        self.cache = ResolutionCache(cache_config or CacheConfig())
        loader = context.loader
        self._product_resolver = ProductResolver(loader, context.provider_id)
        self._delivery_resolver = DeliveryResolver(loader, context.provider_id)
        self._weight_tier_resolver = WeightTierResolver(loader)
        self._zone_resolver = ZoneResolver(validator)
        self._feature_resolver = FeatureResolver(loader)
        self._service_resolver = ServiceResolver(loader)
        self.catalog = PortoCatalog(loader, self._service_resolver)

    @property
    def data_loader(self):
        """@internal Not part of public API — apps must not use."""
        return self.context.loader

    @property
    def product_resolver(self) -> ProductResolver:
        """@internal For pricing via PriceResolver."""
        return self._product_resolver

    @property
    def weight_tier_resolver(self) -> WeightTierResolver:
        """@internal For weight tier resolution"""
        return self._weight_tier_resolver

    def _resolved_mark_profile(self, zone_id: str, service_ids: list[str] | None):
        graph = self.data_loader.resolution_graph
        default = self.data_loader.get_default_mark_profile()
        profile_id = resolve_mark_profile_id(
            mark_edges=graph.mark_edges,
            zone_id=zone_id,
            service_ids=service_ids,
            default_profile_id=default.id if default else None,
        )
        if profile_id:
            found = self.data_loader.get_mark_profile(profile_id)
            if found:
                return found
        return default

    def _bind_requires(
        self,
        product: PortoProduct,
        features: list[Feature],
        service_ids: list[str] | None,
        zone_id: str,
    ) -> frozenset[Requirement]:
        groups: list[tuple[Requirement, ...] | frozenset[Requirement] | list[Requirement]] = [
            product.requires
        ]
        for feat in features:
            groups.append(feat.requires)
            row = self.data_loader.get_feature(feat.id)
            if row:
                groups.append(row.requires)
        selected: list[str] = []
        seen: set[str] = set()
        for raw in service_ids or []:
            sid = str(raw or "").strip()
            if not sid or sid in seen:
                continue
            seen.add(sid)
            selected.append(sid)
        for sid in selected:
            svc = self.data_loader.get_service(sid)
            if svc:
                groups.append(svc.requires)
                for fid in svc.features:
                    row = self.data_loader.get_feature(str(fid))
                    if row:
                        groups.append(row.requires)
        profile = self._resolved_mark_profile(zone_id, selected or service_ids)
        if profile:
            groups.append(profile.requires)
        return merge_requires(*groups)

    def resolve(self, request: ResolutionRequest) -> Porto:
        """Unified resolution pipeline - data-driven, no provider branching"""
        cache_key = self.cache.generate_key(self.context.provider_id, request)

        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        envelope_id = self._envelope_id_from_request(request)

        # 1. Country-level restriction facts — same payload as restrictions.check(country).
        # Region drill-down is only via restrictions.check(country, region).
        destination_restrictions = for_destination(
            self.data_loader,
            request.country_code,
            None,
            provider_id=self.context.provider_id,
        )

        # 2. Zone resolution
        zone_result = self._resolve_zone(request.country_code)
        if not zone_result["is_valid"]:
            raise_destination_invalid(
                f"Invalid country code: {request.country_code}",
                country_code=request.country_code,
                status_code=400,
                details={"errors": zone_result["errors"]},
            )
        zone = zone_result["data"]["zone"]

        # 3. Weight tier resolution
        weight_tier_id = self._weight_tier_resolver.resolve(request.weight)
        if not weight_tier_id:
            raise_too_heavy(
                f"Weight {request.weight}g does not match any weight tier",
                weight=request.weight,
                status_code=400,
            )

        weight_tier = self.data_loader.get_weight_tier(weight_tier_id)
        if not weight_tier:
            raise_data_not_found(
                f"Weight tier {weight_tier_id} not found",
                entity_id=weight_tier_id,
            )

        if request.weight > weight_tier.max_weight:
            raise_too_heavy(
                f"Weight {request.weight}g exceeds limit {weight_tier.max_weight}g",
                weight=request.weight,
                max_weight=weight_tier.max_weight,
                status_code=400,
            )

        # 4–5. Product discovery and selection
        mapped_service_ids: list[str] = []
        selected_kinds: tuple[ServiceKind, ...] = ()
        if request.product_id:
            product = self.data_loader.get_product(request.product_id)
            if not product:
                raise_product_not_found(
                    f"Invalid product_id={request.product_id} for zone={zone.id}, weight_tier={weight_tier_id}",
                    zone_id=zone.id,
                    weight_tier_id=weight_tier_id,
                    product_id=request.product_id,
                    status_code=400,
                )
            if not self._product_resolver.is_valid_combination(
                product.id,
                zone.id,
                weight_tier_id,
            ):
                self._raise_unresolved_product(
                    zone_id=zone.id,
                    weight_tier_id=weight_tier_id,
                    weight=request.weight,
                    message=(
                        f"Invalid product_id={request.product_id} for "
                        f"zone={zone.id}, weight_tier={weight_tier_id}"
                    ),
                    product_id=request.product_id,
                )
            candidates = [product]
            candidates, mapped_service_ids, selected_kinds = (
                self._product_resolver.apply_service_tokens(
                    candidates,
                    None,
                    kinds=request.services,
                    service_ids=request.service_ids,
                    indemnity_tier=request.indemnity_tier,
                    zone_id=zone.id,
                    weight_tier_id=weight_tier_id,
                )
            )
            if not candidates:
                self._raise_unresolved_product(
                    zone_id=zone.id,
                    weight_tier_id=weight_tier_id,
                    weight=request.weight,
                    message=(
                        f"Invalid product_id={request.product_id} for "
                        f"zone={zone.id}, weight_tier={weight_tier_id}"
                    ),
                    product_id=request.product_id,
                )
            product = candidates[0]
        else:
            candidates = self._product_resolver.find_candidates(
                zone.id,
                weight_tier_id,
                envelope_id,
            )
            try:
                candidates, mapped_service_ids, selected_kinds = (
                    self._product_resolver.apply_service_tokens(
                        candidates,
                        None,
                        kinds=request.services,
                        service_ids=request.service_ids,
                        indemnity_tier=request.indemnity_tier,
                        zone_id=zone.id,
                        weight_tier_id=weight_tier_id,
                    )
                )
            except PortoError as exc:
                if exc.code == PortoErrorCode.PORTO_PRODUCT_AMBIGUOUS:
                    self._enrich_ambiguous_error(exc, candidates, zone.id)
                raise
            if not candidates:
                valid_zones = self.data_loader.resolution_graph.links
                self._raise_unresolved_product(
                    zone_id=zone.id,
                    weight_tier_id=weight_tier_id,
                    weight=request.weight,
                    message=(f"No product for zone={zone.id}, weight_tier={weight_tier_id}"),
                    details={"available_products": list(valid_zones.keys())},
                )
            try:
                product = self._product_resolver.select_product(
                    candidates,
                    zone.id,
                    weight_tier_id,
                    delivery_preference=request.delivery_preference,
                    indemnity_tier=request.indemnity_tier,
                    strategy=getattr(self.data_loader.resolution_graph, "strategy", None),
                )
            except PortoError as exc:
                if exc.code == PortoErrorCode.PORTO_PRODUCT_AMBIGUOUS:
                    self._enrich_ambiguous_error(exc, candidates, zone.id)
                raise
            if product is None:
                self._raise_unresolved_product(
                    zone_id=zone.id,
                    weight_tier_id=weight_tier_id,
                    weight=request.weight,
                    message=(f"No product for zone={zone.id}, weight_tier={weight_tier_id}"),
                )

        delivery_hint = self._delivery_resolver.resolve(product, zone.id)

        # 6. Base price lookup
        pricing = self.data_loader.get_price_by_product_zone_weight_tier(
            product.id, zone.id, weight_tier_id
        )
        if not pricing:
            raise_price_not_found(
                f"No price for {product.id} / {zone.id} / {weight_tier_id}",
                product_id=product.id,
                zone_id=zone.id,
                weight_tier_id=weight_tier_id,
                status_code=500,
            )

        # 7. Currency from price row (international USD) or graph default
        row_currency = getattr(pricing, "currency", None)
        if isinstance(row_currency, str) and row_currency.strip():
            currency = row_currency.strip().upper()
        else:
            currency = (
                self.data_loader.resolution_graph.unit.get("currency", "EUR")
                if hasattr(self.data_loader.resolution_graph, "unit")
                else "EUR"
            )

        # 8. Features, dimensions, services
        features_result = self._feature_resolver.resolve(product.id, zone.id)
        services_result = self._service_resolver.resolve(product.id, zone.id)
        if mapped_service_ids:
            self.validate_service_selection(mapped_service_ids, product.id, zone.id)
        requires = self._bind_requires(
            product,
            features_result["data"]["features"],
            mapped_service_ids,
            zone.id,
        )
        profile = self._resolved_mark_profile(zone.id, mapped_service_ids)
        mark_type = profile.mark_type if profile else getattr(product, "mark_type", None)
        tracking = getattr(product, "tracking", None)

        quote = compose_quote(
            product_id=product.id,
            product_amount=pricing.price,
            zone_id=zone.id,
            weight_tier_id=weight_tier_id,
            service_ids=mapped_service_ids,
            lookup_service_price=self.get_service_price,
        )

        porto = Porto(
            product=product,
            zone=zone,
            weight_tier=weight_tier,
            amount=quote.amount,
            currency=currency,
            components=list(quote.components),
            features=features_result["data"]["features"],
            available_services=list(services_result["data"]["services"]),
            is_valid=True,
            warnings=[],
            restrictions=destination_restrictions,
            delivery_hint=delivery_hint,
            mark_type=mark_type,
            tracking=tracking,
            requires=tuple(sorted(requires)),
            services=tuple(selected_kinds),
            service_ids=tuple(mapped_service_ids),
        )

        self.cache.set(cache_key, porto)
        return porto

    def _envelope_id_from_request(self, request: ResolutionRequest) -> str | None:
        if request.envelope_id:
            return request.envelope_id.strip()
        dims = request.dimensions
        if dims is None:
            return None
        for envelope in self.data_loader.list_envelopes():
            same = dims.length == envelope.width and dims.width == envelope.height
            swapped = dims.length == envelope.height and dims.width == envelope.width
            if same or swapped:
                return str(envelope.id)
        return None

    def _resolve_zone(self, country_code: str) -> dict[str, Any]:
        return self._zone_resolver.resolve(country_code)

    def resolve_zone(self, country_code: str) -> PortoZone:
        """
        Resolution primitive: resolve zone from country code.
        Thin wrapper over zone resolution (not data retrieval).
        """
        result = self.validator.validate_country_code(country_code)
        if not result.is_valid or result.data is None:
            raise ValueError(f"Invalid country code: {country_code}")
        return result.data["zone"]  # type: ignore[no-any-return]

    def get_supported_zones(
        self, product_id: str | None = None, envelope_id: str | None = None
    ) -> list[PortoZone]:
        """Zones reachable from the graph, optionally filtered by product or envelope."""
        links = getattr(self.data_loader.resolution_graph, "links", None) or {}
        zone_ids: set[str] = set()
        wanted_envelope = envelope_id.strip().upper() if envelope_id else None
        for graph_product_id, link_data in links.items():
            product = self.data_loader.get_product(graph_product_id)
            if not product:
                continue
            if product_id and product.id != product_id:
                continue
            if wanted_envelope:
                allowed = {eid.upper() for eid in (product.envelope_ids or [])}
                if allowed and wanted_envelope not in allowed:
                    continue
            zone_ids.update(link_data.get("zones", []))
        return [z for zone_id in zone_ids if (z := self.data_loader.get_zone(zone_id)) is not None]

    def _max_graph_weight_for_zone(self, zone_id: str) -> int | None:
        index = self.data_loader.resolution_index
        if index is None:
            return None
        max_seen: int | None = None
        for tier_id in index.weight_tier_ids(zone_id):
            tier = self.data_loader.get_weight_tier(tier_id)
            if tier is None:
                continue
            if max_seen is None or tier.max_weight > max_seen:
                max_seen = tier.max_weight
        return max_seen

    def _raise_unresolved_product(
        self,
        *,
        zone_id: str,
        weight_tier_id: str,
        weight: int,
        message: str,
        product_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> NoReturn:
        max_weight = self._max_graph_weight_for_zone(zone_id)
        if max_weight is not None and weight > max_weight:
            raise_too_heavy(
                f"Weight {weight}g exceeds limit {max_weight}g",
                weight=weight,
                max_weight=max_weight,
                status_code=400,
            )
        raise_product_not_found(
            message,
            zone_id=zone_id,
            weight_tier_id=weight_tier_id,
            product_id=product_id,
            status_code=400,
            details=details,
        )

    def _serialize_delivery_hint(self, hint) -> dict[str, Any] | None:
        if hint is None:
            return None
        return {
            "span": hint.span,
            "days_max": hint.days_max,
            "days_min": hint.days_min,
            "working_days": {
                "market": hint.working_days.market,
                "weekdays": hint.working_days.weekdays,
                "exclude_public_holidays": hint.working_days.exclude_public_holidays,
            },
        }

    def _enrich_ambiguous_error(
        self, exc: PortoError, candidates: list[PortoProduct], zone_id: str
    ) -> None:
        details = dict(exc.details or {})
        enriched = []
        for product in candidates:
            facts = self._product_resolver.candidate_facts(product, zone_id)
            hint = facts.get("delivery_hint")
            enriched.append(
                {
                    "product_id": product.id,
                    "delivery_hint": self._serialize_delivery_hint(hint),
                    "fingerprint": facts.get("fingerprint"),
                    "included_features": facts.get("included_features"),
                    "indemnity": facts.get("indemnity"),
                    "tracking": facts.get("tracking"),
                }
            )
        details["candidates"] = enriched
        exc.details = details

    def clear_cache(self) -> None:
        self.cache.clear()

    def get_cache_stats(self) -> dict[str, int]:
        return {"size": self.cache.size(), "max_size": self.cache.max_size()}

    def list_products(
        self,
        country_from: str | None = None,
        country_to: str | None = None,
    ) -> list[PortoProduct]:
        return self.catalog.list_products(country_from, country_to)

    def get_product(self, product_id: str) -> PortoProduct | None:
        return self.catalog.get_product(product_id)

    def get_product_constraints(self, product_id: str) -> dict[str, Any]:
        return self.catalog.get_product_constraints(product_id)

    def get_graph(self) -> dict[str, Any]:
        return self.catalog.get_graph()

    def list_destination_countries(self) -> list[DestinationCountry]:
        """Catalog read: unique destination country codes from provider zones."""
        return self.catalog.list_destination_countries()

    def list_zones(self) -> list[PortoZone]:
        """Catalog read: zones available for the provider."""
        return self.catalog.list_zones()

    def list_dimensions(self) -> list[dict[str, Any]]:
        """Catalog read: raw dimension specs for envelope matching."""
        return self.catalog.list_dimensions()

    def list_envelopes(self) -> list:
        """Catalog read: envelopes available for the provider."""
        return self.catalog.list_envelopes()

    def list_weight_tiers(self) -> list[PortoWeightTier]:
        """Catalog read: all weight tiers in porto-data."""
        return self.catalog.list_weight_tiers()

    def get_weight_tier(self, weight_tier_id: str) -> PortoWeightTier | None:
        """Catalog read: weight tier lookup by id."""
        return self.catalog.get_weight_tier(weight_tier_id)

    def get_price_by_product_zone_weight_tier(
        self, product_id: str, zone_id: str, weight_tier_id: str
    ) -> PortoPricing | None:
        """Catalog read: price lookup by product/zone/weight tier."""
        return self.catalog.get_price_by_product_zone_weight_tier(
            product_id, zone_id, weight_tier_id
        )

    def get_service_price(self, service_id: str, zone_id: str | None = None) -> int | None:
        """Catalog read: service price by id, and zone when the catalog is zoned."""
        return self.catalog.get_service_price(service_id, zone_id)

    def get_service(self, service_id: str) -> Service | None:
        """Catalog read: service row by id."""
        return self.catalog.get_service(service_id)

    def services_of_kind(self, kind: ServiceKind) -> list[Service]:
        """Catalog read: services whose kind matches."""
        return self.catalog.services_of_kind(kind)

    def list_service_options_for_product_zone(
        self, product_id: str, zone_id: str
    ) -> list[ServiceOption]:
        """Optional add-on services for a product + zone (priced rows for Compose UI)."""
        return self.catalog.list_service_options_for_product_zone(product_id, zone_id)

    def validate_service_selection(
        self,
        service_ids: list[str] | None,
        product_id: str,
        zone_id: str,
    ) -> None:
        """Catalog-backed gate for add-on service ids (porto-data combinable_with)."""
        options = self.list_service_options_for_product_zone(product_id, zone_id)
        validate_service_selection(service_ids, options)

    def get_delivery_hint(self, product_id: str, zone_id: str) -> DeliveryHint | None:
        """Public delivery SLA read for a product in a zone."""
        product = self.get_product(product_id)
        if product is None:
            return None
        return self._delivery_resolver.resolve(product, zone_id)

    def list_wire_ids(self) -> list[str]:
        """Wire ids in graph.edges.wire for the active provider (catalog facet)."""
        return self.catalog.list_wire_ids()


def _bind_execution_models() -> None:
    """Resolve forward refs after Porto exists (execution avoids importing this module at runtime)."""
    from .. import execution as execution_mod
    from ..data.entities.products import PortoProduct

    execution_mod.Porto = Porto  # type: ignore[misc]
    execution_mod.PortoProduct = PortoProduct  # type: ignore[misc]
    execution_mod.PortoMarkRequest.model_rebuild()
    execution_mod.MarkExecution.model_rebuild()


_bind_execution_models()
