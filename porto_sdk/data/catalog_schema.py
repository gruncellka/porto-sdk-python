"""Catalog compatibility gate — porto-data package version is the schema version."""

from __future__ import annotations

from typing import Any

from ..errors import ConfigurationError, PortoErrorCode

# Mirrors SDK manifest range for gruncellka-porto-data (>=min,<max_exclusive).
SUPPORTED_PORTO_DATA_VERSION_MIN = "0.7.0"
SUPPORTED_PORTO_DATA_VERSION_MAX_EXCLUSIVE = "1.0.0"


def _parse_semver(version: str) -> tuple[int, int, int] | None:
    parts = version.strip().split(".")
    if len(parts) < 2:
        return None
    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return None
    if major < 0 or minor < 0 or patch < 0:
        return None
    return major, minor, patch


def _cmp(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return (a > b) - (a < b)


def assert_catalog_schema_supported(
    metadata: dict[str, Any], *, path: str = "metadata.json"
) -> str:
    """Raise if metadata.project.version is outside the SDK support range.

    The porto-data **package version** is the catalog schema version — one number.
    Returns the validated version string.
    """
    project = metadata.get("project")
    raw = project.get("version") if isinstance(project, dict) else None
    parsed = _parse_semver(raw) if isinstance(raw, str) else None
    min_v = _parse_semver(SUPPORTED_PORTO_DATA_VERSION_MIN)
    max_v = _parse_semver(SUPPORTED_PORTO_DATA_VERSION_MAX_EXCLUSIVE)
    assert min_v is not None and max_v is not None

    details = {
        "porto_data_version": raw,
        "supported_min": SUPPORTED_PORTO_DATA_VERSION_MIN,
        "supported_max_exclusive": SUPPORTED_PORTO_DATA_VERSION_MAX_EXCLUSIVE,
        "path": path,
    }

    if parsed is None:
        raise ConfigurationError(
            "porto-data metadata.json is missing a valid project.version. "
            "Upgrade gruncellka-porto-data to "
            f">={SUPPORTED_PORTO_DATA_VERSION_MIN},<{SUPPORTED_PORTO_DATA_VERSION_MAX_EXCLUSIVE}.",
            PortoErrorCode.PORTO_DATA_INVALID,
            details=details,
        )

    if _cmp(parsed, min_v) < 0:
        raise ConfigurationError(
            f"porto-data package version {raw} is older than this SDK supports "
            f"(>={SUPPORTED_PORTO_DATA_VERSION_MIN},<{SUPPORTED_PORTO_DATA_VERSION_MAX_EXCLUSIVE}). "
            "Upgrade porto-data.",
            PortoErrorCode.PORTO_DATA_TOO_OLD,
            details=details,
        )

    if _cmp(parsed, max_v) >= 0:
        raise ConfigurationError(
            f"porto-data package version {raw} is newer than this SDK supports "
            f"(>={SUPPORTED_PORTO_DATA_VERSION_MIN},<{SUPPORTED_PORTO_DATA_VERSION_MAX_EXCLUSIVE}). "
            "Upgrade the Porto SDK, or pin porto-data within the supported range.",
            PortoErrorCode.PORTO_DATA_TOO_NEW,
            details=details,
        )

    return raw  # type: ignore[return-value]
