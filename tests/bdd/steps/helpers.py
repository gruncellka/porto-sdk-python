"""Shared helpers for BDD step definitions."""

from __future__ import annotations

from typing import Any

from tests.support.bound_provider import bound_provider

PROVIDER_HOME_COUNTRY = {
    "deutschepost": "DE",
    "ukrposhta": "UA",
    "laposte": "FR",
    "swisspost": "CH",
}

# Example country per catalog zone — maps CLI "data price" zone args onto public price().
ZONE_EXAMPLE_COUNTRY: dict[str, dict[str, str]] = {
    "deutschepost": {
        "domestic": "DE",
        "zone_1_eu": "FR",
        "zone_2_europe": "UA",
        "world": "US",
    },
    "laposte": {
        "domestic": "FR",
        "zone_1_eu": "BE",
        "world": "US",
    },
    "ukrposhta": {
        "domestic": "UA",
        "world": "US",
    },
    "swisspost": {
        "domestic": "CH",
        "zone_1_eu": "DE",
        "world": "US",
    },
}


def weight_from_context(context: dict[str, Any], default: int = 20) -> int:
    return int(context.get("weight", context.get("letter_weight", default)))


def country_from_context(context: dict[str, Any], default: str = "DE") -> str:
    return str(context.get("destination_country", default))


def provider_id_from_context(context: dict[str, Any], default: str = "deutschepost") -> str:
    return str(context.get("provider_id") or default)


def provider_home_country(context: dict[str, Any]) -> str:
    return PROVIDER_HOME_COUNTRY.get(provider_id_from_context(context), "DE")


def country_for_zone(provider_id: str, zone_id: str) -> str:
    by_provider = ZONE_EXAMPLE_COUNTRY.get(provider_id) or {}
    if zone_id in by_provider:
        return by_provider[zone_id]
    return PROVIDER_HOME_COUNTRY.get(provider_id, "DE")


def product_to_dict(product: Any) -> dict[str, Any]:
    return {
        "id": product.id,
        "name": product.name,
        "label": product.label,
        "envelope_ids": list(product.envelope_ids),
        "zones": list(product.zones),
    }


def zone_to_dict(zone: Any) -> dict[str, Any]:
    return {
        "id": zone.id,
        "name": zone.name,
        "country_codes": list(zone.country_codes),
    }


def envelope_to_dict(envelope: Any) -> dict[str, Any]:
    return {
        "id": envelope.id,
        "width": envelope.width,
        "height": envelope.height,
    }


def service_to_dict(service: Any) -> dict[str, Any]:
    return {
        "id": service.id,
        "kind": service.kind,
        "name": service.name,
        "features": list(service.features),
    }


def feature_to_dict(feature: Any) -> dict[str, Any]:
    return {
        "id": feature.id,
        "kind": feature.kind,
        "name": feature.name,
        "label": feature.label,
    }


def bound(context: dict[str, Any]):
    return bound_provider(context["client"], provider_id_from_context(context))


def resolve_kwargs_from_context(context: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    kinds = overrides.get("services", context.get("services_kinds"))
    service_ids = overrides.get("service_ids", context.get("service_ids"))
    if service_ids and not kinds:
        kinds = _service_kinds_for_ids(context, service_ids)
    payload: dict[str, Any] = {
        "country_code": overrides.get("country_code", country_from_context(context)),
        "weight": overrides.get("weight", weight_from_context(context)),
        "envelope_id": overrides.get("envelope_id", context.get("envelope_id")),
        "product_id": overrides.get("product_id", context.get("product_id")),
        "delivery_preference": overrides.get(
            "delivery_preference", context.get("delivery_preference")
        ),
        "services": kinds,
        "service_ids": service_ids or None,
        "indemnity_tier": overrides.get("indemnity_tier", context.get("indemnity_tier")),
    }
    return {key: value for key, value in payload.items() if value is not None}


def _service_kinds_for_ids(context: dict[str, Any], service_ids: list[str]) -> list[str]:
    loader = getattr(context["client"], "_data_loader", None)
    kinds: list[str] = []
    for service_id in service_ids:
        kind = None
        if loader is not None:
            service = loader.get_service(service_id)
            kind = getattr(service, "kind", None) if service is not None else None
        if kind:
            kinds.append(str(kind))
    # unique, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for kind in kinds:
        if kind not in seen:
            seen.add(kind)
            out.append(kind)
    return out


def public_resolve(context: dict[str, Any], **overrides: Any):
    return bound(context).resolve(**resolve_kwargs_from_context(context, **overrides))


def public_price(context: dict[str, Any], **overrides: Any):
    return bound(context).price(**resolve_kwargs_from_context(context, **overrides))


def resolve_price(context: dict[str, Any]) -> int:
    pricing = public_price(context)
    context["pricing"] = pricing
    context["price"] = pricing.amount
    context["quoted_amount"] = pricing.amount
    return pricing.amount


def product_reference_amount(context: dict[str, Any], product_id: str) -> int:
    """Quoted amount for a catalog product via public options(), not size buckets."""
    home = country_from_context(context, provider_home_country(context))
    client = bound(context)
    for weight in (20, 50, 100, 500, 1000, 2000):
        for row in client.options(country_code=home, weight=weight):
            if row.id == product_id and row.amount is not None:
                return int(row.amount)
    raise AssertionError(f"public options() did not yield product {product_id!r}")
