"""Parser for mappings.json."""

from typing import Any

DEFAULT_PROVIDER = "deutschepost"


def parse_mappings_to_pairs(
    raw: Any,
    provider: str = DEFAULT_PROVIDER,
) -> list[tuple[str, str]]:
    """Parse mappings from raw JSON and yield (schema_path, data_path) pairs."""
    pairs: list[tuple[str, str]] = []
    mappings = (raw.get("mappings") if isinstance(raw, dict) else None) or raw
    if not mappings or not isinstance(mappings, dict):
        return pairs

    # Global mappings
    global_mappings = mappings.get("global")
    if isinstance(global_mappings, dict):
        for schema_path, data_path in global_mappings.items():
            if isinstance(schema_path, str) and isinstance(data_path, str):
                pairs.append((schema_path, data_path))

    # Policy mappings (markets, jurisdictions, restrictions)
    policy_mappings = mappings.get("policy")
    if isinstance(policy_mappings, dict):
        for schema_path, data_path in policy_mappings.items():
            if isinstance(schema_path, str) and isinstance(data_path, str):
                pairs.append((schema_path, data_path))

    # Formats bundle (envelopes, layouts, addresses)
    formats_mappings = mappings.get("formats")
    if isinstance(formats_mappings, dict):
        for schema_path, data_path in formats_mappings.items():
            if isinstance(schema_path, str) and isinstance(data_path, str):
                pairs.append((schema_path, data_path))

    # Provider registry
    registry_mappings = mappings.get("registry")
    if isinstance(registry_mappings, dict):
        for schema_path, data_path in registry_mappings.items():
            if isinstance(schema_path, str) and isinstance(data_path, str):
                pairs.append((schema_path, data_path))

    # Provider mappings
    providers = mappings.get("providers")
    provider_mappings = providers.get(provider, {}) if isinstance(providers, dict) else {}
    if isinstance(provider_mappings, dict):
        for schema_path, data_path in provider_mappings.items():
            if isinstance(schema_path, str) and isinstance(data_path, str):
                pairs.append((schema_path, data_path))

    return pairs
