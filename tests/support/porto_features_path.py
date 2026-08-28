"""
Resolve path to porto-features (BDD features and fixtures).
Uses the installed gruncellka-porto-features package; PORTO_FEATURES_PATH is an explicit override.
"""

import os
from pathlib import Path


def get_porto_features_root() -> Path:
    """Root directory of porto-features (contains features/ and fixtures/)."""
    env_path = os.environ.get("PORTO_FEATURES_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists() and (p / "features").exists():
            return p.resolve()

    for module_name in ("gruncellka_porto_features", "porto_features"):
        try:
            pkg = __import__(module_name)
            pkg_file = getattr(pkg, "__file__", None)
            if pkg_file is not None:
                root = Path(pkg_file).resolve().parent
                if (root / "features").exists():
                    return root
        except ImportError:
            continue

    raise ValueError(
        "porto-features not found. Install: pip install gruncellka-porto-features, "
        "or set PORTO_FEATURES_PATH to the porto-features directory (e.g. for development)."
    )


def get_features_dir() -> Path:
    """Directory containing .feature files."""
    return get_porto_features_root() / "features"


def get_fixtures_dir() -> Path:
    """Directory containing test fixtures."""
    return get_porto_features_root() / "fixtures"


def _is_porto_data_root(path: Path) -> bool:
    return (path / "mappings.json").exists() or (path / "metadata.json").exists()


def get_porto_data_path() -> str:
    """
    Path to porto-data catalog root for BDD/integration tests.

    Same as production: explicit PORTO_DATA_PATH, otherwise the installed
    gruncellka-porto-data package. Local catalog checkouts are swapped via
    ``pip install -e``, not filesystem path discovery.
    """
    env_path = os.environ.get("PORTO_DATA_PATH")
    if env_path:
        candidate = Path(env_path).expanduser().resolve()
        if _is_porto_data_root(candidate):
            return str(candidate)
        raise FileNotFoundError(
            f"PORTO_DATA_PATH={env_path} is set but is not a porto-data catalog root."
        )

    try:
        from porto_sdk.data.porto_data_registry import find_porto_data_path

        return find_porto_data_path()
    except ValueError as exc:
        raise FileNotFoundError(
            "porto-data not found. Install: pip install gruncellka-porto-data, "
            "or set PORTO_DATA_PATH."
        ) from exc
