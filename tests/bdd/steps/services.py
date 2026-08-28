"""Step definitions for services.feature — public resolve path only."""

from __future__ import annotations

from pytest_bdd import parsers, then


def _available_services(context) -> list:
    porto = context["resolved"]
    return list(getattr(porto, "available_services", None) or [])


def _service_field(service, field: str):
    if isinstance(service, dict):
        return field in service
    return hasattr(service, field)


@then(parsers.parse('available services should include "{service_id}"'))
def available_services_include(service_id: str, context):
    ids = {row["id"] if isinstance(row, dict) else row.id for row in _available_services(context)}
    assert service_id in ids


@then(parsers.parse('each available service should have field "{field}"'))
def each_available_service_has_field(field: str, context):
    rows = _available_services(context)
    assert rows
    for row in rows:
        assert _service_field(row, field)
