"""
Porto Data Loader - Loads and provides access to porto-data files

Explicit mapping from porto-data JSON schemas to Python types.
Loads the provider graph.json first to understand dependencies and relationships.

porto-data remains pure JSON - all type definitions are in SDKs.

Architecture:
- BaseLoader: Common file loading, checksum verification, dependency resolution
- Entity Loaders: Each entity has its own loader (products, zones, prices, etc.)
- Main Loader: Orchestrates entity loaders and provides unified API
"""

from datetime import date
from pathlib import Path
from typing import Any, Collection

from ..config import DEFAULT_PROVIDER
from .base_loader import BaseLoader
from .entities.addresses import AddressesLoader, AddressJurisdictionForm
from .entities.dimensions import DimensionsLoader
from .entities.envelopes import EnvelopesLoader, PortoEnvelope
from .entities.features import Feature, FeaturesLoader
from .entities.jurisdictions import JurisdictionsLoader
from .entities.layouts import EnvelopeLayout, LayoutsLoader
from .entities.markets import MarketsLoader, PortoMarket
from .entities.marks import MarkAssetSize, MarkCalibration, MarkProfile, MarkRect, MarksLoader
from .entities.prices import PortoPricing, PricesLoader
from .entities.products import PortoProduct, ProductsLoader
from .entities.providers_registry import PortoProvider, ProvidersLoader
from .entities.restrictions import PostageRestriction, RestrictionsLoader
from .entities.rules import RulesLoader
from .entities.services import Service, ServicesLoader
from .entities.weight_tiers import PortoWeightTier, WeightTiersLoader
from .entities.zones import PortoZone, ZonesLoader
from .file_type_registry import FileTypeRegistry
from .porto_data_loader import ValidatedPortoDataLoader
from .resolution_index import ResolutionIndex

# Explicit type definitions matching porto-data JSON Schema structure
# See PORTO_DATA_MAPPING.md for mapping documentation
# All entity types are now imported from entity modules above


# Entity types from metadata.json - matches entity keys
PortoEntityType = str  # Type: Literal['products', 'services', 'prices', 'zones', 'weight_tiers', 'dimensions', 'features', 'restrictions', 'resolution_graph']


class PortoDataLoader:
    """
    Porto Data Loader with metadata.json and provider graph.json integration

    Loads metadata.json to understand entity structure, then the provider graph.json,
    then loads files in dependency order.
    Uses lookup rules and links for validation.

    Architecture:
    - Uses BaseLoader for common operations (file loading, checksum verification)
    - Uses entity loaders for each entity type (products, zones, prices, etc.)
    - Main loader orchestrates and provides unified API

    Args:
        data_path: Path to porto-data directory
        verify_checksums: Enable checksum verification using metadata.json (default: True)
    """

    def __init__(
        self,
        data_path: str,
        verify_checksums: bool = True,
        strict_mode: bool = True,
        provider: str = DEFAULT_PROVIDER,
    ):
        data_path_obj = Path(data_path)
        self._validated_files: dict[str, dict[str, Any]] = {}
        self.provider_id = provider.strip().lower()

        # Initialize base loader for common operations
        self._base_loader = BaseLoader(data_path_obj, verify_checksums)

        # Initialize entity loaders
        checksum_map = self._base_loader.checksum_map
        self._products_loader = ProductsLoader(data_path_obj, checksum_map)
        self._zones_loader = ZonesLoader(data_path_obj, checksum_map)
        self._weight_tiers_loader = WeightTiersLoader(data_path_obj, checksum_map)
        self._prices_loader = PricesLoader(data_path_obj, checksum_map)
        self._dimensions_loader = DimensionsLoader(data_path_obj, checksum_map)
        self._features_loader = FeaturesLoader(data_path_obj, checksum_map)
        self._services_loader = ServicesLoader(data_path_obj, checksum_map)
        self._restrictions_loader = RestrictionsLoader(data_path_obj, checksum_map)
        self._envelopes_loader = EnvelopesLoader(data_path_obj, checksum_map)
        self._layouts_loader = LayoutsLoader(data_path_obj, checksum_map)
        self._addresses_loader = AddressesLoader(data_path_obj, checksum_map)
        self._marks_loader = MarksLoader(data_path_obj, checksum_map)
        self._providers_loader = ProvidersLoader(data_path_obj, checksum_map)
        self._markets_loader = MarketsLoader(data_path_obj, checksum_map)
        self._jurisdictions_loader = JurisdictionsLoader(data_path_obj, checksum_map)
        self._rules_loader = RulesLoader(data_path_obj, checksum_map)
        self._file_type_registry = FileTypeRegistry(self)
        self.resolution_index: ResolutionIndex | None = None

        # 1. Validate and load all mapped porto-data once at initialization.
        if strict_mode:
            validated_loader = ValidatedPortoDataLoader(
                data_path_obj, verify_checksums, provider=self.provider_id
            )
            validated = validated_loader.load()
            self._validated_files = validated["files"]
            self._base_loader._metadata = validated["metadata"]
            self._base_loader._build_checksum_map()

            # 2. Load resolution graph
            self.resolution_graph = validated["registries"].resolution_graph
            # 3. Load all files in dependency order
            self._load_all_data_in_order()
            self._load_registry_entities_from_validated()
            self._build_resolution_index()
        else:
            # Relaxed mode — skip schema/checksum validation; load provider graph + entities.
            self._base_loader.verify_checksums = False
            metadata = self._base_loader.load_metadata()
            if metadata:
                from .catalog_schema import assert_catalog_schema_supported

                assert_catalog_schema_supported(metadata)
            graph_path = f"providers/{self.provider_id}/graph.json"
            graph_data = self._base_loader.load_data(graph_path)
            from .graph_normalize import normalize_resolution_graph

            self.resolution_graph = normalize_resolution_graph(graph_data)
            relaxed_files = [
                "policy/markets.json",
                "policy/jurisdictions.json",
                "formats/envelopes.json",
                "formats/layouts.json",
                "formats/addresses.json",
                "providers.json",
                f"providers/{self.provider_id}/products.json",
                f"providers/{self.provider_id}/zones.json",
                f"providers/{self.provider_id}/weights.json",
                f"providers/{self.provider_id}/prices/products.json",
                f"providers/{self.provider_id}/prices/services.json",
                f"providers/{self.provider_id}/marks.json",
                f"providers/{self.provider_id}/features.json",
                f"providers/{self.provider_id}/services.json",
            ]
            for relative_path in relaxed_files:
                file_name = relative_path.split("/")[-1]
                try:
                    data = self._base_loader.load_data(relative_path)
                    self._load_file_by_name(file_name, data=data, source_path=relative_path)
                except RuntimeError:
                    continue
            self._build_resolution_index()

    @property
    def data_path(self) -> Path:
        return self._base_loader.data_path

    def _resolve_graph_file_path(self, filename: str) -> str:
        if filename.startswith(("policy/", "formats/", "providers/")):
            return filename
        provider_path = f"providers/{self.provider_id}/{filename}"
        if provider_path in self._validated_files:
            return provider_path
        candidate = self._base_loader.data_path / provider_path
        if candidate.is_file():
            return provider_path
        return filename

    def _load_all_data_in_order(self) -> None:
        """
        Load all porto-data files in dependency order

        Uses BaseLoader for dependency resolution and routes to entity loaders.
        """
        load_order = self._base_loader.calculate_load_order(self.resolution_graph)

        for file_name in load_order:
            if file_name == "graph.json":
                continue  # Already loaded

            self._load_file_by_name(file_name)

    def _load_registry_entities_from_validated(self) -> None:
        for relative_path in ("providers.json",):
            payload = self._validated_files.get(relative_path)
            if not payload:
                continue
            file_name = relative_path.split("/")[-1]
            self._load_file_by_name(file_name, data=payload, source_path=relative_path)

    def _load_file_by_name(
        self,
        filename: str,
        *,
        data: dict[str, Any] | None = None,
        source_path: str | None = None,
    ) -> None:
        """
        Load a file by name and dispatch it to the entity loader for its ``file_type``.

        Files without a ``file_type`` field are resolved by filename; anything the
        registry cannot dispatch is a hard error.
        """
        if data is None:
            resolved_path = source_path or self._resolve_graph_file_path(filename)
            if filename in self._validated_files:
                data = self._validated_files[filename]
            elif resolved_path in self._validated_files:
                data = self._validated_files[resolved_path]
            else:
                data = self._base_loader.load_data(resolved_path)
        file_type = data.get("file_type")
        if not file_type:
            inferred = {
                "providers.json": "providers",
                "envelopes.json": "envelopes",
                "layouts.json": "layouts",
                "addresses.json": "addresses",
            }
            file_type = inferred.get(filename)
        if not file_type:
            raise RuntimeError(f"File {filename} missing 'file_type' field")

        result = self._file_type_registry.dispatch(file_type, data)
        if not result.handled:
            raise RuntimeError(f"Unsupported porto-data file_type: {file_type}")

    def _build_resolution_index(self) -> None:
        links = getattr(self.resolution_graph, "links", None) or {}
        self.resolution_index = ResolutionIndex.build(
            links, self._products_loader.get_all_products()
        )

    # Product query methods - now delegate to ProductsLoader
    def get_product(self, product_id: str) -> PortoProduct | None:
        """Get product by ID"""
        return self._products_loader.get_product(product_id)

    def get_all_products(self) -> list[PortoProduct]:
        """Get all products"""
        return self._products_loader.get_all_products()

    # Zone query methods - now delegate to ZonesLoader
    def get_zone_by_country_code(self, country_code: str) -> PortoZone | None:
        """Get zone by country code"""
        return self._zones_loader.get_zone_by_country_code(country_code)

    def get_zone(self, zone_id: str) -> PortoZone | None:
        """Get zone by ID"""
        return self._zones_loader.get_zone(zone_id)

    def get_all_zones(self) -> list[PortoZone]:
        """Get all zones"""
        return self._zones_loader.get_all_zones()

    # Weight tier query methods - now delegate to WeightTiersLoader
    def get_weight_tier(self, tier_id: str) -> PortoWeightTier | None:
        """Get weight tier by ID"""
        return self._weight_tiers_loader.get_weight_tier(tier_id)

    def get_all_weight_tiers(self) -> list[PortoWeightTier]:
        """Get all weight tiers (for resolution primitives)"""
        return list(self._weight_tiers_loader.get_data())

    def get_price_by_product_zone_weight_tier(
        self, product_id: str, zone_id: str, weight_tier_id: str
    ) -> PortoPricing | None:
        """
        Get price by product_id + zone + weight_tier (lookup_rules.price_lookup).
        Use this instead of accessing _prices_loader directly.
        """
        return self._prices_loader.get_pricing(product_id, zone_id, weight_tier_id)

    def get_service_price(self, service_id: str, zone_id: str | None = None) -> int | None:
        """
        Get price for a service by catalog id (and zone when rows are zoned).
        Returns amount in cents, or None if not found in porto-data.
        """
        return self._prices_loader.get_service_price(service_id, zone_id)

    def provider_jurisdiction_tokens(self, provider_id: str | None = None) -> frozenset[str]:
        pid = (provider_id or self.provider_id or "").strip().lower()
        provider = self.get_provider(pid)
        if provider is None:
            return frozenset()
        country = (provider.country or "").strip().upper()
        if country in self._jurisdictions_loader.eu_members():
            return frozenset({"EU"})
        if country == "CH":
            return frozenset({"CH"})
        if country == "UA":
            return frozenset({"UA"})
        return frozenset()

    def check_restrictions(
        self,
        country_code: str,
        product_id: str | None = None,
        zone_id: str | None = None,
        region_code: str | None = None,
        *,
        jurisdictions: Collection[str] | None = None,
        as_of: date | None = None,
    ) -> PostageRestriction:
        """
        Check geo restrictions for country code and optional region.
        """
        tokens = (
            frozenset(jurisdictions)
            if jurisdictions is not None
            else self.provider_jurisdiction_tokens()
        )
        return self._restrictions_loader.check_restrictions(
            country_code,
            product_id,
            zone_id,
            region_code,
            jurisdictions=tokens,
            as_of=as_of,
        )

    def classify_restrictions(
        self,
        country_code: str,
        region_code: str | None = None,
        *,
        jurisdictions: Collection[str] | None = None,
        as_of: date | None = None,
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """Legal and routing catalog projection at destination precision (internal)."""
        tokens = (
            frozenset(jurisdictions)
            if jurisdictions is not None
            else self.provider_jurisdiction_tokens()
        )
        return self._restrictions_loader.classify_restrictions(
            country_code,
            region_code,
            jurisdictions=tokens,
            as_of=as_of,
        )

    def restrictions_catalog(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Raw legal/routing country maps from porto-data (storage shape)."""
        return self._restrictions_loader.get_data()

    def get_features_for_product(self, product_id: str) -> list[Feature]:
        """Get features available for a product"""
        return self._features_loader.get_features_for_product(product_id)

    def get_features_for_zone(self, zone_id: str) -> list[Feature]:
        """Get features available for a zone"""
        return self._features_loader.get_features_for_zone(zone_id)

    def get_dimensions_for_product(self, product_id: str) -> list[dict[str, Any]]:
        """Get dimension specifications for a product"""
        product = self.get_product(product_id)
        if not product:
            return []
        return self._dimensions_loader.get_dimensions_for_product(product_id, product.envelope_ids)

    def get_dimension_by_id(self, dimension_id: str) -> dict[str, Any] | None:
        """Get dimension spec by ID."""
        return self._dimensions_loader.get_dimension(dimension_id)

    def get_all_dimensions(self) -> list[dict[str, Any]]:
        """Get all envelope/format dimensions from porto-data."""
        return self._dimensions_loader.get_all_dimensions()

    def get_services_for_product(self, product_id: str) -> list[Service]:
        """Get services available for a product"""
        return self._services_loader.get_services_for_product(product_id)

    def get_services_for_zone(self, zone_id: str) -> list[Service]:
        """Get services available for a zone"""
        return self._services_loader.get_services_for_zone(zone_id)

    def get_all_services(self) -> list[Service]:
        """Get all services for the current provider"""
        return self._services_loader.get_all_services()

    def get_service(self, service_id: str) -> Service | None:
        """Get a service by id, or None if unknown."""
        return self._services_loader.get_service(service_id)

    def get_all_features(self) -> list[Feature]:
        """Get all features for the current provider"""
        return self._features_loader.get_all_features()

    def get_feature(self, feature_id: str) -> Feature | None:
        return self._features_loader.get_feature(feature_id)

    def get_envelope(self, envelope_id: str) -> PortoEnvelope | None:
        return self._envelopes_loader.get_envelope(envelope_id)

    def list_envelopes(self) -> list[PortoEnvelope]:
        return self._envelopes_loader.list_envelopes()

    def get_layout(self, jurisdiction: str, envelope_id: str) -> EnvelopeLayout | None:
        return self._layouts_loader.get_layout(jurisdiction, envelope_id)

    def get_address_form(self, jurisdiction: str) -> AddressJurisdictionForm | None:
        return self._addresses_loader.get_form(jurisdiction)

    def get_mark_profile(self, profile_id: str) -> MarkProfile | None:
        return self._marks_loader.get_profile(profile_id)

    def get_default_mark_profile(self) -> MarkProfile | None:
        return self._marks_loader.get_default_profile()

    def get_mark_placement(self, envelope_id: str) -> MarkRect | None:
        return self._marks_loader.get_placement(envelope_id)

    def get_mark_calibration(
        self,
        *,
        wire: str,
        mark_profile: str,
        mime_type: str = "image/png",
        dpi: int = 300,
    ) -> MarkCalibration | None:
        """``mark_profile`` = ``calibrations[].mark_profile`` (wire layout token)."""
        return self._marks_loader.get_calibration(
            wire=wire, mark_profile=mark_profile, mime_type=mime_type, dpi=dpi
        )

    def get_mark_calibration_asset_size(
        self,
        *,
        wire: str,
        mark_profile: str,
        mark_profile_id: str | None = None,
        mime_type: str = "image/png",
        dpi: int = 300,
    ) -> MarkAssetSize | None:
        return self._marks_loader.get_calibration_asset_size(
            wire=wire,
            mark_profile=mark_profile,
            mark_profile_id=mark_profile_id,
            mime_type=mime_type,
            dpi=dpi,
        )

    def list_providers(self) -> list[PortoProvider]:
        return self._providers_loader.list_providers()

    def get_provider(self, provider_id: str) -> PortoProvider | None:
        return self._providers_loader.get_provider(provider_id)

    def get_market(self, country_code: str) -> PortoMarket | None:
        return self._markets_loader.get_market(country_code)

    def get_timezone_for_country(self, country_code: str) -> str | None:
        return self._jurisdictions_loader.get_timezone_for_country(country_code)

    def get_timezone_by_country(self) -> dict[str, str]:
        return self._jurisdictions_loader.get_timezone_by_country()

    def country_codes(self) -> list[str]:
        return self._jurisdictions_loader.country_codes()

    def get_country_code_3(self, country_code: str) -> str | None:
        return self._jurisdictions_loader.get_country_code_3(country_code)
