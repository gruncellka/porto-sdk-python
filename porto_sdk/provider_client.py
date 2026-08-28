"""Immutable bound execution context for one postal provider."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .adapters.execution_registry import (
    get_default_wire_id,
    get_execution_adapter,
    resolve_active_wire_for,
    supports_billing,
    supports_execution,
)
from .adapters.tracking.adapter import TrackingAdapter, TrackingKind, get_tracking_adapter
from .config import ProviderRuntimeConfig, normalize_provider_id
from .data.domain_validator import DomainIds
from .data.loader import PortoDataLoader
from .kinds import FeatureKind, ServiceKind
from .services.billing import BillingService
from .services.porto_execution import PortoExecution
from .services.porto_resolver import Porto, PortoResolver
from .services.pricing import Pricing
from .services.pricing import price as lookup_price
from .services.product_option_types import ProductOption
from .services.provider_capabilities import ProviderCapabilitiesService
from .services.restrictions import RestrictionsService
from .services.tracking import TrackingService
from .services.validation import LetterValidationService
from .states import CapabilityState, capability_state

if TYPE_CHECKING:
    from .client import PortoClient
    from .execution import ExecutionParameters, PortoMark, PortoMarkRequest


@dataclass(frozen=True)
class ProviderCapabilities:
    provider_id: str
    mark: CapabilityState
    wallet: CapabilityState
    track: CapabilityState
    tracking_kind: TrackingKind


class ProviderClient:
    """
    Immutable bound view of exactly one provider execution context.

    Use ``PortoClient.provider(id)`` — never pass provider_id on individual verbs.
    """

    def __init__(
        self,
        *,
        root: PortoClient,
        provider_id: str,
        runtime: ProviderRuntimeConfig,
        data_loader: PortoDataLoader,
        data_path: str,
        resolver: PortoResolver,
    ) -> None:
        self._root = root
        self.provider_id = normalize_provider_id(provider_id)
        self._runtime = runtime
        self._data_loader = data_loader
        self._data_path = data_path

        validator = DomainIds(data_loader)
        porto_resolver = resolver

        wire_id = resolve_active_wire_for(
            self.provider_id,
            runtime.wires,
            data_path,
        ) or get_default_wire_id(self.provider_id, data_path)

        self._execution_adapter = get_execution_adapter(
            self.provider_id,
            runtime.wires,
            data_path=data_path,
            http_client=getattr(root, "_http_client", None),
        )
        bind = getattr(self._execution_adapter, "set_country_code_3_lookup", None)
        if callable(bind):
            from .services.jurisdictions import JurisdictionsService

            bind(JurisdictionsService(data_loader).country_code_3)
        self._tracking_adapter: TrackingAdapter = get_tracking_adapter(
            self.provider_id,
            wire_id=wire_id,
            data_path=data_path,
        )

        validation = LetterValidationService(
            porto_resolver,
            validator,
            root.address,
        )
        porto_execution = PortoExecution(
            data_loader,
            self._execution_adapter,
            porto_resolver,
            validation,
        )
        self._resolver = porto_resolver
        self._execution = porto_execution
        self.track: TrackingService = TrackingService(self._tracking_adapter)
        self.restrictions: RestrictionsService = RestrictionsService(
            data_loader, provider_id=self.provider_id
        )
        self._billing = BillingService(
            root,
            provider_id=self.provider_id,
            wires=runtime.wires,
            adapter=self._execution_adapter,
        )

    @property
    def wallet(self) -> BillingService:
        return self._billing

    def resolve(
        self,
        *,
        country_code: str,
        weight: int,
        envelope_id: str | None = None,
        product_id: str | None = None,
        services: list[ServiceKind] | None = None,
        service_ids: list[str] | None = None,
        delivery_preference: str | None = None,
        indemnity_tier: str | None = None,
    ) -> Porto:
        from .services.porto_resolver import ResolutionRequest
        from .services.resolution.types import DeliveryPreference

        preference: DeliveryPreference | None = None
        if delivery_preference in ("fastest", "cheapest", "economy"):
            preference = delivery_preference  # type: ignore[assignment]
        return self._resolver.resolve(
            ResolutionRequest(
                country_code=country_code,
                weight=weight,
                envelope_id=envelope_id,
                product_id=product_id,
                services=services,
                service_ids=service_ids,
                delivery_preference=preference,
                indemnity_tier=indemnity_tier,
            )
        )

    def price(
        self,
        *,
        weight: int,
        country_code: str,
        product_id: str | None = None,
        envelope_id: str | None = None,
        indemnity_tier: str | None = None,
        services: list[ServiceKind] | None = None,
        service_ids: list[str] | None = None,
        delivery_preference: str | None = None,
    ) -> Pricing:
        from .services.resolution.types import DeliveryPreference

        preference: DeliveryPreference | None = None
        if delivery_preference in ("fastest", "cheapest", "economy"):
            preference = delivery_preference  # type: ignore[assignment]
        return lookup_price(
            self._resolver,
            weight=weight,
            country_code=country_code,
            product_id=product_id,
            envelope_id=envelope_id,
            indemnity_tier=indemnity_tier,
            services=services,
            service_ids=service_ids,
            delivery_preference=preference,
        )

    def options(
        self,
        *,
        country_code: str,
        weight: int,
        envelope_id: str | None = None,
    ) -> list[ProductOption]:
        from .services.product_options import list_product_options as _list

        return _list(
            self._resolver,
            country_code=country_code,
            weight=weight,
            envelope_id=envelope_id,
        )

    def estimate(
        self,
        *,
        product_id: str,
        country_code: str,
        weight: int,
    ):
        from .services.product_options import estimate_for_product

        return estimate_for_product(
            self._resolver,
            product_id=product_id,
            country_code=country_code,
            weight=weight,
        )

    def advise(
        self,
        *,
        weight: float,
        selected_product_id: str | None = None,
        candidate_product_ids: list[str] | None = None,
    ):
        from .services.product_advice import recommend_product_for_weight

        return recommend_product_for_weight(
            self._resolver,
            weight=weight,
            selected_product_id=selected_product_id,
            candidate_product_ids=candidate_product_ids,
        )

    async def prepare(self, request: PortoMarkRequest):
        return await self._execution.prepare(request)

    async def bytes(self, mark: PortoMark, **kwargs) -> bytes:
        return await self._execution.bytes(mark, **kwargs)

    async def _prepare(self, *args: Any, **kwargs: Any):
        return await self._execution.prepare(*args, **kwargs)

    async def mark(
        self,
        request: PortoMarkRequest | Sequence[PortoMarkRequest],
        execution: ExecutionParameters | None = None,
    ) -> PortoMark | list[PortoMark]:
        return await self._execution.mark(request, execution)

    def capabilities(self) -> ProviderCapabilities:
        wires = self._runtime.wires
        can_mark = supports_execution(
            self.provider_id,
            "mark",
            wires=wires,
            data_path=self._data_path,
        )
        can_wallet = supports_billing(
            self.provider_id,
            "wallet",
            wires=wires,
            data_path=self._data_path,
        )
        return ProviderCapabilities(
            provider_id=self.provider_id,
            mark=capability_state(supported=can_mark),
            track=capability_state(supported=self._tracking_adapter.supports_tracking),
            wallet=capability_state(supported=can_wallet),
            tracking_kind=self._tracking_adapter.tracking_kind,
        )

    def can(self, feature: FeatureKind, context: dict[str, Any] | None = None) -> bool:
        return ProviderCapabilitiesService(self._data_loader).can_use_feature(
            self.provider_id,
            feature,
            context,  # type: ignore[arg-type]
        )
