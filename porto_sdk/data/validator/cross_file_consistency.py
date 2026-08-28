"""Cross-file consistency validation."""

from ...errors import DataError, PortoErrorCode
from ..registries import PortoDataRegistries


def _data_error(message: str) -> None:
    raise DataError(message, PortoErrorCode.PORTO_DATA_INVALID, status_code=500)


def validate_cross_file_consistency(registries: PortoDataRegistries) -> None:
    """Validate cross-file references between porto-data entities."""
    dimension_ids = {str(d.get("id")) for d in registries.dimensions}
    product_ids = {str(p.id) for p in registries.products}
    zone_ids = {str(z.id) for z in registries.zones}
    weight_tier_ids = {str(w.id) for w in registries.weight_tiers}
    service_ids = {str(s.get("id")) for s in registries.services}
    feature_ids = set()
    for feature in registries.features:
        if feature.get("id") is not None:
            feature_ids.add(str(feature.get("id")))
        porto_id = feature.get("porto_id")
        if porto_id is not None:
            feature_ids.add(str(porto_id))

    for product in registries.products:
        if product.weight_tier is not None and product.weight_tier not in weight_tier_ids:
            _data_error(
                f"Product '{product.id}' references unknown weight tier '{product.weight_tier}'."
            )
        for zone_id in product.zones or []:
            if zone_id not in zone_ids:
                _data_error(f"Product '{product.id}' references unknown zone '{zone_id}'.")
        for dimension_id in product.envelope_ids or []:
            if dimension_ids and dimension_id not in dimension_ids:
                _data_error(f"Product '{product.id}' references unknown envelope '{dimension_id}'.")

    for price in registries.prices:
        if price.product_id not in product_ids:
            _data_error(f"Price entry references unknown product '{price.product_id}'.")
        if price.zone not in zone_ids:
            _data_error(f"Price entry references unknown zone '{price.zone}'.")
        if price.weight_tier not in weight_tier_ids:
            _data_error(f"Price entry references unknown weight tier '{price.weight_tier}'.")

    for sp in registries.service_prices:
        service_id = str(sp.get("service_id"))
        if service_id not in service_ids:
            _data_error(
                f"Service price entry references unknown service '{service_id}' (must exist in services)."
            )

    resolution_graph = registries.resolution_graph
    global_settings = resolution_graph.global_settings or {}
    configured_service_ids = {str(s) for s in global_settings.get("available_services", [])}
    for service_id in configured_service_ids:
        if service_id not in service_ids:
            _data_error(
                f"resolution_graph.global_settings.available_services references unknown service '{service_id}'."
            )

    for service in registries.services:
        for feature_id in service.get("features", []):
            if str(feature_id) not in feature_ids:
                _data_error(
                    f"Service '{service.get('id')}' references unknown feature '{feature_id}'."
                )

    for product_id, links in (registries.resolution_graph.links or {}).items():
        if product_id not in product_ids:
            _data_error(f"resolution_graph references unknown product '{product_id}'.")
        for zone_id in links.get("zones", []):
            if zone_id not in zone_ids:
                _data_error(
                    f"resolution_graph for product '{product_id}' references unknown zone '{zone_id}'."
                )
        for weight_tier_id in links.get("weight_tiers", []):
            if weight_tier_id not in weight_tier_ids:
                _data_error(
                    f"resolution_graph for product '{product_id}' references unknown weight tier '{weight_tier_id}'."
                )
