import json
from pathlib import Path
from typing import Any

from ..errors import ConfigurationError, PortoErrorCode
from .catalog_schema import assert_catalog_schema_supported
from .graph_normalize import normalize_resolution_graph
from .porto_data_validator import PortoDataValidator
from .registries import PortoDataRegistries

DEFAULT_PROVIDER = "deutschepost"


def _restriction_rows(document: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in ("legal", "routing", "operational"):
        block = document.get(name)
        if isinstance(block, dict):
            for country, payload in block.items():
                if isinstance(payload, dict):
                    rows.append({"collection": name, "country_code": country, **payload})
    return rows


class ValidatedPortoDataLoader:
    def __init__(self, data_path: Path, verify_checksums: bool, provider: str = DEFAULT_PROVIDER):
        self.data_path = data_path
        self.verify_checksums = verify_checksums
        self.provider = provider

    def load(self) -> dict[str, Any]:
        metadata = self._load_json("metadata.json")
        assert_catalog_schema_supported(metadata)
        mappings = self._load_json("mappings.json")
        validator = PortoDataValidator(
            self.data_path,
            metadata,
            mappings,
            self.verify_checksums,
            provider=self.provider,
        )
        validator.validate_paths()

        files: dict[str, dict[str, Any]] = {}
        for schema_path, data_path in validator.get_mapping_pairs():
            file_name = data_path.split("/")[-1]
            data = validator.validate_mapped_file(data_path, schema_path)
            files[data_path] = data
            if file_name not in files:
                files[file_name] = data

        registries = self._build_registries(files)
        validator.validate_cross_file_consistency(registries)
        return {
            "metadata": metadata,
            "mappings": mappings,
            "files": files,
            "registries": registries,
        }

    def _build_registries(self, files: dict[str, dict[str, Any]]) -> PortoDataRegistries:
        from .entities.products import _parse_delivery, _parse_indemnity
        from .loader import PortoPricing, PortoProduct, PortoWeightTier, PortoZone

        provider_prefix = f"providers/{self.provider}/"

        def file_at(relative_path: str, fallback_name: str | None = None) -> dict[str, Any]:
            return (
                files.get(f"{provider_prefix}{relative_path}")
                or (files.get(fallback_name) if fallback_name else None)
                or {}
            )

        products = [
            PortoProduct(
                id=p.get("id"),
                name=p.get("name"),
                envelope_ids=p.get("envelope_ids") or [],
                zones=p.get("zones") or [],
                weight_tier=p.get("weight_tier"),
                effective_from=p.get("effective_from"),
                effective_to=p.get("effective_to"),
                provider_mappings=p.get("provider_mappings"),
                mark_type=p.get("mark_type"),
                tracking=p.get("tracking"),
                delivery=_parse_delivery(p.get("delivery")),
                included_features=list(p.get("included_features") or []),
                indemnity=_parse_indemnity(p.get("indemnity")),
            )
            for p in file_at("products.json", "products.json").get("products", [])
        ]

        zones = [
            PortoZone(
                id=z.get("id"),
                name=z.get("name", ""),
                description=z.get("description", ""),
                country_codes=z.get("country_codes", []),
            )
            for z in file_at("zones.json", "zones.json").get("zones", [])
        ]

        weights_raw = file_at("weights.json", "weight_tiers.json")
        weight_tiers_raw = weights_raw.get("weights") or weights_raw.get("weight_tiers") or {}
        if isinstance(weight_tiers_raw, dict):
            weight_tiers = [
                PortoWeightTier(
                    id=tier_id,
                    max_weight=tier_data.get("max", tier_data.get("max_weight", 0)),
                )
                for tier_id, tier_data in weight_tiers_raw.items()
            ]
        else:
            weight_tiers = [
                PortoWeightTier(
                    id=wt.get("id"),
                    max_weight=wt.get("max", wt.get("max_weight", 0)),
                )
                for wt in weight_tiers_raw
            ]

        prices_raw = file_at("prices/products.json").get("product_prices") or files.get(
            "prices.json", {}
        ).get("prices", {}).get("product_prices", [])
        prices = [
            PortoPricing(
                product_id=pp.get("product_id"),
                zone=pp.get("zone"),
                weight_tier=pp.get("weight_tier"),
                price=(pp.get("price") or [{}])[0].get("amount", 0),
                effective_from=(pp.get("price") or [{}])[0].get("effective_from"),
                effective_to=(pp.get("price") or [{}])[0].get("effective_to"),
            )
            for pp in prices_raw
        ]

        resolution_graph_raw = file_at("graph.json", "graph.json") or files.get("graph.json") or {}
        if not resolution_graph_raw:
            raise ConfigurationError(
                "Missing graph.json in validated porto-data files",
                PortoErrorCode.PORTO_DATA_NOT_FOUND,
                status_code=500,
            )
        resolution_graph = normalize_resolution_graph(resolution_graph_raw)

        return PortoDataRegistries(
            dimensions=files.get("dimensions.json", {}).get("dimensions", []),
            products=products,
            prices=prices,
            zones=zones,
            weight_tiers=weight_tiers,
            services=file_at("services.json", "services.json").get("services", []),
            features=file_at("features.json", "features.json").get("features", []),
            restrictions=_restriction_rows(
                files.get("policy/restrictions.json") or files.get("restrictions.json") or {}
            ),
            resolution_graph=resolution_graph,
            service_prices=(
                file_at("prices/services.json").get("service_prices")
                or files.get("prices.json", {}).get("prices", {}).get("service_prices", [])
            ),
        )

    def _load_json(self, relative_path: str) -> dict[str, Any]:
        path = self.data_path / relative_path
        try:
            return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
        except Exception as error:
            raise ConfigurationError(
                f"Failed to load required porto-data file '{relative_path}': {error}",
                PortoErrorCode.PORTO_DATA_NOT_FOUND,
                status_code=500,
            ) from error
