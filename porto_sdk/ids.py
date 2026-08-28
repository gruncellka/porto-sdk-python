"""Branded identifiers that must not be swapped at type-check time."""

from __future__ import annotations

from typing import NewType

ProviderId = NewType("ProviderId", str)
WireId = NewType("WireId", str)
TrackingNumber = NewType("TrackingNumber", str)
ExternalMarkId = NewType("ExternalMarkId", str)


def as_provider_id(value: str) -> ProviderId:
    return ProviderId(value.strip().lower())


def as_wire_id(value: str) -> WireId:
    return WireId(value.strip().lower())


def as_tracking_number(value: str) -> TrackingNumber:
    return TrackingNumber(value.strip())


def as_external_mark_id(value: str) -> ExternalMarkId:
    return ExternalMarkId(value.strip())
