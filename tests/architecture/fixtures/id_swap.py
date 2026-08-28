"""Compile-time fixture: ProviderId must not be accepted as WireId.

This module is not collected as a test. Architecture tests run mypy against it
and expect a type error.
"""

from datetime import timedelta

from porto_sdk.ids import ProviderId, WireId, as_provider_id, as_wire_id


def needs_wire(wire: WireId) -> WireId:
    return wire


def needs_timeout(timeout: timedelta) -> timedelta:
    return timeout


def type_error_provider_as_wire() -> WireId:
    provider: ProviderId = as_provider_id("deutschepost")
    return needs_wire(provider)


def type_error_milliseconds_int_as_timeout() -> timedelta:
    return needs_timeout(30_000)


def valid_wire_and_timeout() -> tuple[WireId, timedelta]:
    return needs_wire(as_wire_id("internetmarke")), needs_timeout(timedelta(seconds=30))
