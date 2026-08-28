"""
Porto-data validator - orchestrates path, checksum, schema, and cross-file validation.
Uses small focused modules; single supported metadata shape (global + providers).
"""

import json
from pathlib import Path
from typing import Any

from ..errors import ConfigurationError, DataError, PortoErrorCode
from .registries import PortoDataRegistries
from .validator import (
    ensure_path_is_file,
    normalize_metadata,
    parse_mappings_to_pairs,
    validate_cross_file_consistency,
    validate_schema,
    verify_checksum,
)


class PortoDataValidator:
    """Validates porto-data files and cross-file consistency."""

    def __init__(
        self,
        data_path: Path,
        metadata: Any,
        mappings: Any,
        verify_checksums: bool,
        provider: str = "deutschepost",
    ):
        try:
            self._metadata = normalize_metadata(metadata)
        except ValueError as err:
            raise ConfigurationError(
                str(err),
                PortoErrorCode.PORTO_DATA_INVALID,
                status_code=500,
            ) from err
        self._data_path = Path(data_path)
        self._verify_checksums = verify_checksums
        self._provider = provider
        self._mapping_pairs = parse_mappings_to_pairs(mappings, provider)

    def validate_paths(self) -> None:
        """Validate that all mapped paths exist and are files."""
        for schema_path, data_path in self._mapping_pairs:
            ensure_path_is_file(self._data_path, schema_path)
            ensure_path_is_file(self._data_path, data_path)

    def validate_mapped_file(
        self, data_relative_path: str, schema_relative_path: str
    ) -> dict[str, Any]:
        """Load, validate schema, and optionally verify checksum for a mapped file."""
        data = self._load_json(data_relative_path)
        schema = self._load_json(schema_relative_path)
        if self._verify_checksums:
            verify_checksum(self._data_path, self._metadata, data_relative_path)
            verify_checksum(self._data_path, self._metadata, schema_relative_path)
        validate_schema(
            data,
            schema,
            data_relative_path,
            schema_relative_path,
            data_root=self._data_path,
        )
        return data

    def validate_cross_file_consistency(self, registries: PortoDataRegistries) -> None:
        """Validate cross-file references between entities."""
        validate_cross_file_consistency(registries)

    def get_mapping_pairs(self) -> list[tuple[str, str]]:
        """Return list of (schema_path, data_path) pairs."""
        return list(self._mapping_pairs)

    def _load_json(self, relative_path: str) -> dict[str, Any]:
        absolute_path = self._data_path / relative_path
        try:
            return json.loads(absolute_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
        except Exception as error:
            raise DataError(
                f"Failed to parse JSON file '{relative_path}': {error}",
                PortoErrorCode.PORTO_DATA_INVALID,
                status_code=500,
            ) from error
