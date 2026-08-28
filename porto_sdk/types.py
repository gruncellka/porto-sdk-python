"""
Core type definitions for Porto SDK
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Dimensions(BaseModel):
    """Physical dimensions in mm. Provider-specific limits live in porto-data."""

    length: int = Field(ge=1, le=2000, description="Length in mm")
    width: int = Field(ge=1, le=2000, description="Width in mm")
    height: int = Field(ge=0, le=2000, description="Height in mm")
    thickness: int | None = Field(None, ge=0, le=2000, description="Thickness in mm (optional)")

    model_config = {
        "extra": "forbid",  # Reject extra fields for safety
        "validate_assignment": True,
    }


class Address(BaseModel):
    """Address model. Jurisdiction forms are validated in AddressResolver; provider wire ACL in adapters.

    Street vs post_box: catalog forms are XOR — set ``post_box`` *or* street/house_number, not both.
    """

    name: str = Field(..., min_length=1, max_length=100, description="Recipient/sender name")
    street: str | None = Field(
        None, max_length=100, description="Street name (street form; omit for post_box)"
    )
    house_number: str | None = Field(
        None, max_length=20, description="House number (street form; omit for post_box)"
    )
    post_box: str | None = Field(
        None, max_length=40, description="Post box id (post_box form; omit for street)"
    )
    postal_code: str = Field(..., min_length=1, max_length=16, description="Postal / ZIP code")
    locality: str = Field(
        ..., min_length=1, max_length=100, description="Locality (town / place / city)"
    )
    country_code: str = Field(
        ..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code"
    )
    region_code: str | None = Field(
        None,
        max_length=10,
        description="Optional region code (ISO 3166-2 preferred)",
    )

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        """Ensure country code is uppercase"""
        return v.strip().upper()

    @field_validator("postal_code")
    @classmethod
    def validate_postal_code(cls, v: str) -> str:
        """Normalize whitespace; do not assume DE 5-digit format at the type layer."""
        cleaned = v.strip().replace(" ", "")
        if not cleaned:
            raise ValueError("Postal code must not be empty")
        return cleaned

    @field_validator("name", "street", "house_number", "post_box", "locality")
    @classmethod
    def trim_whitespace(cls, v: str | None) -> str | None:
        """Trim whitespace from string fields; empty optional strings become None."""
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned if cleaned else None

    model_config = {
        "extra": "forbid",  # Reject extra fields for safety
        "validate_assignment": True,
    }


class ValidationResult(BaseModel):
    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    data: dict | None = None


class MarkRequest(BaseModel):
    """Internal adapter DTO. Product identity lives on frozen Porto, not here.

    Address presence is decided by ``Porto.requires``, not by a registered-service type.
    """

    destination: Address | None = None
    origin: Address | None = None
    value: int
    zone: str | None = None  # Zone code (e.g., 'domestic', 'zone_1', 'zone_2')
    idempotency_key: str | None = None
    wire_code: int | str | None = None  # internal catalog product code for the active wire


class TrackingState(str, Enum):
    CREATED = "created"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    RETURNED = "returned"
    UNDELIVERABLE = "undeliverable"


class TrackingEvent(BaseModel):
    event_id: str
    provider_id: str
    provider_code: str | None = None
    provider_label: str | None = None
    occurred_at: str
    received_at: str
    status: TrackingState
    location: str | None = None
    description: str | None = None


class TrackingStatus(BaseModel):
    tracking_number: str
    provider_id: str
    tracking_kind: Literal["shipment", "stamp"]
    status: TrackingState
    last_update: str
    poll_received_at: str
    location: str | None = None
    next_steps: list[str] | None = None
    estimated_delivery: str | None = None
    history: list[TrackingEvent] = []
