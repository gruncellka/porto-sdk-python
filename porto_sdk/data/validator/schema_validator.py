"""Schema validation with caching compiled schemas by path.

Cross-file $ref (e.g. products.schema.json) must resolve against the local
catalog, not the schema $id GitHub URL — otherwise unpublished vocabulary
changes fail validation against whatever main currently publishes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from referencing import Registry, Resource

from ...errors import DataError, PortoErrorCode

_schema_cache: dict[str, Draft202012Validator] = {}
_GITHUB_SCHEMA_PREFIX = (
    "https://raw.githubusercontent.com/gruncellka/porto-data/refs/heads/main/porto_data/schemas/"
)


def _cache_key(schema_path: str, data_path: str) -> str:
    return f"{schema_path}::{data_path}"


def create_validator() -> None:
    """No-op for Python - jsonschema validators are created per-schema."""


def _local_registry(data_root: Path | None) -> Registry:
    registry: Registry = Registry()
    if data_root is None:
        return registry
    schemas_dir = Path(data_root) / "schemas"
    if not schemas_dir.is_dir():
        return registry
    for sibling in schemas_dir.glob("*.json"):
        try:
            contents = json.loads(sibling.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(contents, dict):
            continue
        resource = Resource.from_contents(contents)
        uris = {sibling.name, f"schemas/{sibling.name}", _GITHUB_SCHEMA_PREFIX + sibling.name}
        schema_id = contents.get("$id")
        if isinstance(schema_id, str) and schema_id.strip():
            uris.add(schema_id.strip())
        for uri in uris:
            registry = registry.with_resource(uri, resource)
    return registry


def validate_schema(
    data: dict[str, Any],
    schema: dict[str, Any],
    data_relative_path: str,
    schema_relative_path: str,
    *,
    data_root: Path | str | None = None,
) -> None:
    """Validate data against schema. Caches compiled validator by path."""
    cache_key = _cache_key(schema_relative_path, data_relative_path)
    if cache_key not in _schema_cache:
        root = Path(data_root) if data_root is not None else None
        _schema_cache[cache_key] = Draft202012Validator(
            schema,
            registry=_local_registry(root),
        )
    validator = _schema_cache[cache_key]
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        details = "; ".join(f"{list(err.path)} {err.message}" for err in errors)
        raise DataError(
            f"Schema validation failed for '{data_relative_path}' using '{schema_relative_path}': {details}",
            PortoErrorCode.PORTO_DATA_INVALID,
            status_code=500,
        )
