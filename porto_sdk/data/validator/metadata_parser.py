"""Metadata parser - single supported shape: global + providers."""

from collections.abc import Iterator
from typing import Any


def _walk_entities(node: Any) -> Iterator[dict[str, Any]]:
    """Recursively yield entity dicts that contain data/schema entries."""
    if not node or not isinstance(node, dict):
        return
    if "data" in node or "schema" in node:
        yield node
        return
    for value in node.values():
        yield from _walk_entities(value)


def iter_metadata_entities(metadata: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Iterate over all entity entries from metadata (global + all providers)."""
    global_entities = metadata.get("global") or {}
    if isinstance(global_entities, dict):
        yield from _walk_entities(global_entities)
    providers = metadata.get("providers") or {}
    if isinstance(providers, dict):
        for provider_entities in providers.values():
            yield from _walk_entities(provider_entities)


def has_supported_metadata_shape(metadata: Any) -> bool:
    """Check if metadata has the supported shape (global + providers)."""
    if not metadata or not isinstance(metadata, dict):
        return False
    global_entities = metadata.get("global")
    providers = metadata.get("providers")
    return (
        global_entities is not None
        and isinstance(global_entities, dict)
        and providers is not None
        and isinstance(providers, dict)
    )


def normalize_metadata(raw: Any) -> dict[str, Any]:
    """Normalize metadata to supported shape (global + providers)."""
    if has_supported_metadata_shape(raw):
        return {"global": raw["global"], "providers": raw["providers"]}
    if isinstance(raw, dict) and isinstance(raw.get("providers"), dict):
        global_entities: dict[str, Any] = {}
        for section in ("policy", "formats", "registry"):
            if section in raw and isinstance(raw[section], dict):
                global_entities[section] = raw[section]
        if global_entities:
            return {"global": global_entities, "providers": raw["providers"]}
    raise ValueError(
        "Metadata must have global+providers (or policy/formats/registry + providers). "
        "Partial metadata is not supported."
    )
