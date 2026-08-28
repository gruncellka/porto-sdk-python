"""
Porto Data Registry - Central porto-data discovery, validation, and loading

All porto-data file access is centralized here. Config stays pure.
Registry is the single source of truth for porto-data.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .loader import PortoDataLoader

if TYPE_CHECKING:
    from ..config import PortoConfig

DEFAULT_PROVIDER = "deutschepost"

# Public catalog discovery error — no install-command hints.
PORTO_DATA_CATALOG_UNRESOLVED = (
    "Porto data catalog could not be resolved.\n\n"
    "Install the porto-data package or provide an explicit dataPath / PORTO_DATA_PATH override."
)


def find_porto_data_path() -> str:
    """
    Find porto-data catalog root from the installed package.

    Order: installed ``gruncellka-porto-data`` / ``porto_data`` only.
    Override via ``PortoConfig.data_path`` / ``PORTO_DATA_PATH`` at the registry layer.
    The catalog is never copied into the SDK package.
    """
    try:
        from porto_data import get_package_root

        root = get_package_root()
        if (root / "mappings.json").exists():
            return str(root)
    except ImportError:
        pass

    for module_name in ("gruncellka_porto_data", "porto_data"):
        try:
            pkg = __import__(module_name)
            pkg_file = getattr(pkg, "__file__", None)
            if pkg_file is not None:
                root = Path(pkg_file).resolve().parent
                if (root / "mappings.json").exists():
                    return str(root)
        except ImportError:
            continue

    raise ValueError(PORTO_DATA_CATALOG_UNRESOLVED)


def get_valid_providers_from_mappings(data_path: str) -> frozenset[str]:
    """
    Load valid provider ids from porto-data mappings.json.
    Returns keys of mappings.providers (e.g. deutschepost, swisspost).
    """
    path = Path(data_path) / "mappings.json"
    if not path.exists():
        return frozenset()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    raw = data.get("mappings", data)
    providers = raw.get("providers", {}) if isinstance(raw, dict) else {}
    if not isinstance(providers, dict):
        return frozenset()
    return frozenset(k for k in providers if isinstance(k, str))


def validate_provider(
    provider: str | None,
    data_path: str,
) -> str:
    """
    Validate provider exists in porto-data mappings.
    Returns normalized provider id or raises ValueError.
    """
    p = (provider or DEFAULT_PROVIDER).strip().lower()
    valid_providers = get_valid_providers_from_mappings(data_path)
    if valid_providers and p not in valid_providers:
        raise ValueError(
            f"Invalid provider '{provider}'. Must be one of: {sorted(valid_providers)}. "
            f"(from porto-data mappings at {data_path})"
        )
    return p


class PortoDataRegistry:
    """
    Central porto-data registry: discovery, validation, loading.

    - Resolves data_path (auto-discovery if not provided)
    - Validates provider against mappings
    - Loads core + provider datasets
    - Exposes loader to services
    """

    def __init__(self, config: "PortoConfig"):
        self._config = config
        self._data_path: str = ""
        self._provider_id: str = ""
        self._loader: PortoDataLoader | None = None

    @property
    def data_path(self) -> str:
        """Resolved porto-data path (discovered or from config)."""
        if not self._data_path:
            self._resolve_data_path()
        return self._data_path

    @property
    def provider_id(self) -> str:
        """Validated provider id."""
        if not self._provider_id:
            ids = self._config.configured_provider_ids()
            catalog = next(iter(sorted(ids)), None)
            self._provider_id = validate_provider(catalog, self.data_path)
        return self._provider_id

    @property
    def loader(self) -> PortoDataLoader:
        """Loaded porto-data loader (core + provider datasets)."""
        if self._loader is None:
            self._loader = PortoDataLoader(
                self.data_path,
                provider=self.provider_id,
                strict_mode=self._config.strict_data_validation,
            )
        return self._loader

    def loader_for(self, provider_id: str) -> PortoDataLoader:
        """Provider-scoped loader sharing the same porto-data path."""
        pid = validate_provider(provider_id, self.data_path)
        return PortoDataLoader(
            self.data_path,
            provider=pid,
            strict_mode=self._config.strict_data_validation,
        )

    def get_metadata(self) -> dict[str, Any] | None:
        """Load metadata.json from porto-data. Returns None if not found."""
        return self.loader._base_loader.load_metadata()

    def _resolve_data_path(self) -> None:
        """Resolve data_path from config or auto-discovery."""
        path = self._config.data
        if path and str(path).strip():
            self._data_path = str(path).strip()
        else:
            self._data_path = find_porto_data_path()
