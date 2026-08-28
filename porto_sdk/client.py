"""
Porto Client - Main SDK entry point
"""

from .adapters import (
    DataFactoryAdapter,
    OfflineDataFactoryAdapter,
    get_address_adapter,
    get_execution_adapter,
    get_tracking_adapter,
)
from .adapters.protocols.execution import ExecutionAdapter
from .adapters.unavailable_execution import UnavailableExecutionAdapter
from .config import (
    NormalizedPortoConfig,
    PortoConfig,
    ProviderRuntimeConfig,
    WireConfig,
    normalize_provider_id,
)
from .data.context import PostalResolutionContext
from .data.domain_validator import DomainIds
from .data.loader import PortoDataLoader
from .data.porto_data_registry import PortoDataRegistry, get_valid_providers_from_mappings
from .errors import PortoError, PortoErrorCode
from .provider_client import ProviderClient
from .services.address import AddressResolver
from .services.envelope_resolver import EnvelopeResolverService, Envelopes
from .services.jurisdictions import JurisdictionsService
from .services.porto_resolver import PortoResolver
from .services.providers import ProvidersService
from .services.restrictions import RestrictionsService
from .services.validation import LetterValidationService
from .transport.http_client import HttpClient, Transport


class PortoClient:
    """
    Main SDK client — postal platform entry point.

    Public surface:
    - client.envelopes.identify(...)
    - client.restrictions.check(...)
    - client.address.validate(...)
    - client.providers.list(...)
    - client.provider(id).resolve / price / mark / wallet / track
    """

    def __init__(self, config: PortoConfig | None = None, *, transport: Transport | None = None):
        self.config: PortoConfig = config if config is not None else PortoConfig()
        self._normalized: NormalizedPortoConfig = self.config.normalize()
        registry = PortoDataRegistry(self.config)
        data_loader = registry.loader
        validator = DomainIds(data_loader)

        policy = self._normalized.resolved_transport()
        self._http_client: Transport = transport or HttpClient(
            timeout=policy.timeout,
            retries=policy.retries,
            backoff=policy.backoff,
        )
        self._execution_adapter: ExecutionAdapter = UnavailableExecutionAdapter(
            self._normalized.default_provider, "none"
        )
        self._tracking_adapter = self._execution_adapter
        self._datafactory_api: DataFactoryAdapter | OfflineDataFactoryAdapter = (
            OfflineDataFactoryAdapter()
        )

        self._resolvers: dict[str, PortoResolver] = {}
        porto_resolver = self._resolver_for(data_loader.provider_id, data_loader)
        self._update_adapters(data_loader)

        self.address: AddressResolver = AddressResolver(data_loader, validator)
        validation = LetterValidationService(porto_resolver, validator, self.address)
        self.envelopes: Envelopes = EnvelopeResolverService(validation, data_loader)
        self.restrictions: RestrictionsService = RestrictionsService(data_loader)
        self.providers: ProvidersService = ProvidersService(data_loader)
        self.jurisdictions: JurisdictionsService = JurisdictionsService(data_loader)

        self._data_loader = data_loader
        self._registry = registry
        self._provider_clients: dict[str, ProviderClient] = {}

    def _resolver_for(self, provider_id: str, data_loader: PortoDataLoader) -> PortoResolver:
        pid = normalize_provider_id(provider_id)
        existing = self._resolvers.get(pid)
        if existing is not None:
            return existing
        validator = DomainIds(data_loader)
        resolver = PortoResolver(
            context=PostalResolutionContext(loader=data_loader, provider_id=pid),
            validator=validator,
            cache_config=self._normalized.cache,
        )
        self._resolvers[pid] = resolver
        return resolver

    def _catalog_provider_id(self) -> str:
        return self._normalized.default_provider

    def _bound(self) -> ProviderClient:
        return self.provider(self._catalog_provider_id())

    def provider(self, provider_id: str) -> ProviderClient:
        """Return immutable bound execution context for one catalog provider."""
        pid = normalize_provider_id(provider_id)
        catalog = get_valid_providers_from_mappings(self._registry.data_path)
        allowlist = self._normalized.allowlist
        if catalog and pid not in catalog:
            raise PortoError(
                f"Provider '{pid}' is unknown in the catalog or excluded by the providers allowlist.",
                PortoErrorCode.PORTO_PROVIDER_NOT_CONFIGURED,
                status_code=400,
                provider=pid,
                details={
                    "provider_id": pid,
                    "configured_providers": sorted(catalog),
                },
                retryable=False,
            )
        if allowlist is not None and pid not in allowlist:
            raise PortoError(
                f"Provider '{pid}' is unknown in the catalog or excluded by the providers allowlist.",
                PortoErrorCode.PORTO_PROVIDER_NOT_CONFIGURED,
                status_code=400,
                provider=pid,
                details={
                    "provider_id": pid,
                    "configured_providers": sorted(allowlist),
                },
                retryable=False,
            )
        if pid not in self._provider_clients:
            runtime = self._normalized.runtime_for(pid)
            loader = self._registry.loader_for(pid)
            data_path = self._normalized.data or str(loader.data_path)
            self._provider_clients[pid] = ProviderClient(
                root=self,
                provider_id=pid,
                runtime=runtime,
                data_loader=loader,
                data_path=data_path,
                resolver=self._resolver_for(pid, loader),
            )
        return self._provider_clients[pid]

    def _update_adapters(self, data_loader=None) -> None:
        loader = data_loader or getattr(self, "_data_loader", None)
        data_path = self._normalized.data or (str(loader.data_path) if loader else None)
        provider = self._catalog_provider_id()
        wires = self._normalized.wires_for(provider)
        self._execution_adapter = get_execution_adapter(
            provider,
            wires,
            data_path=data_path,
            http_client=self._http_client,
        )
        if loader is not None:
            bind = getattr(self._execution_adapter, "set_country_code_3_lookup", None)
            if callable(bind):
                from .services.jurisdictions import JurisdictionsService

                bind(JurisdictionsService(loader).country_code_3)
        self._tracking_adapter = get_tracking_adapter(
            provider,
            wires,
            data_path=data_path,
        )
        self._datafactory_api = get_address_adapter(
            provider,
            wires,
            client=self,
            http_client=self._http_client,
        )

    def update_credentials(
        self,
        wires: dict[str, WireConfig] | None = None,
    ) -> None:
        catalog = self._catalog_provider_id()
        providers = dict(self._normalized.providers)
        providers[catalog] = ProviderRuntimeConfig(wires=wires)
        self.config = self.config.model_copy(update={"providers": providers})
        self._normalized = self.config.normalize()
        self._provider_clients.clear()
        self._update_adapters(self._data_loader)

    def clear_cache(self) -> None:
        for resolver in self._resolvers.values():
            resolver.clear_cache()
