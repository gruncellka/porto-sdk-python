"""Checksum validation with explicit checks for None, empty string."""

import hashlib
from pathlib import Path
from typing import Any

from ...errors import ConfigurationError, DataError, PortoErrorCode
from .metadata_parser import iter_metadata_entities


def _is_checksum_valid(value: Any) -> bool:
    return isinstance(value, str) and len(value) > 0


def find_expected_checksum(metadata: dict[str, Any], relative_path: str) -> str | None:
    """Find expected checksum for a path."""
    for entity in iter_metadata_entities(metadata):
        data_info = entity.get("data", {})
        schema_info = entity.get("schema", {})
        if data_info.get("path") == relative_path:
            checksum = data_info.get("checksum")
            return checksum if _is_checksum_valid(checksum) else None
        if schema_info.get("path") == relative_path:
            checksum = schema_info.get("checksum")
            return checksum if _is_checksum_valid(checksum) else None
    return None


def verify_checksum(data_path: Path, metadata: dict[str, Any], relative_path: str) -> None:
    """Validate checksum for a file. Explicit errors for different invalid states."""
    found = False
    checksum_value = None
    for entity in iter_metadata_entities(metadata):
        data_info = entity.get("data", {})
        schema_info = entity.get("schema", {})
        if data_info.get("path") == relative_path:
            found = True
            checksum_value = data_info.get("checksum")
            break
        if schema_info.get("path") == relative_path:
            found = True
            checksum_value = schema_info.get("checksum")
            break

    if not found:
        raise ConfigurationError(
            f"No checksum entry found in metadata for '{relative_path}'.",
            PortoErrorCode.PORTO_DATA_INVALID,
            status_code=500,
        )
    if checksum_value is None:
        raise ConfigurationError(
            f"Checksum entry for '{relative_path}' has undefined checksum.",
            PortoErrorCode.PORTO_DATA_INVALID,
            status_code=500,
        )
    if checksum_value == "":
        raise ConfigurationError(
            f"Checksum entry for '{relative_path}' is incomplete (empty or invalid).",
            PortoErrorCode.PORTO_DATA_INVALID,
            status_code=500,
        )
    if not isinstance(checksum_value, str):
        raise ConfigurationError(
            f"Checksum entry for '{relative_path}' is incomplete (empty or invalid).",
            PortoErrorCode.PORTO_DATA_INVALID,
            status_code=500,
        )

    absolute_path = data_path / relative_path
    actual = hashlib.sha256(absolute_path.read_bytes()).hexdigest()
    if actual != checksum_value:
        raise DataError(
            f"Checksum mismatch for '{relative_path}'. Data file does not match metadata. Run 'make metadata' in porto-data to regenerate checksums.",
            PortoErrorCode.PORTO_DATA_CORRUPTED,
            status_code=422,  # Unprocessable Entity - data integrity failure, not server error
            details={"expected": checksum_value, "actual": actual},
        )
