"""
Pydantic validation schemas for INTERNETMARKE API
These schemas ensure runtime safety and compliance
"""

from pydantic import BaseModel, Field, field_validator


class InternetmarkeAddressSchema(BaseModel):
    """Validated address schema for INTERNETMARKE API"""

    name: str = Field(..., min_length=1, max_length=100, description="Recipient/sender name")
    street: str = Field(..., min_length=1, max_length=100, description="Street name")
    houseNumber: str = Field(..., min_length=1, max_length=10, description="House number")
    postalCode: str = Field(..., pattern=r"^\d{5}$", description="5-digit postal code")
    city: str = Field(..., min_length=1, max_length=100, description="City name")
    countryCode: str = Field(
        ..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code"
    )
    regionCode: str | None = Field(None, max_length=10, description="Optional region code")

    @field_validator("countryCode")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        """Ensure country code is uppercase"""
        return v.strip().upper()

    @field_validator("postalCode")
    @classmethod
    def validate_postal_code(cls, v: str) -> str:
        """Ensure postal code is 5 digits, zero-padded if needed"""
        cleaned = v.strip().replace(" ", "").replace("-", "")
        if not cleaned.isdigit():
            raise ValueError("Postal code must contain only digits")
        return cleaned.zfill(5)

    @field_validator("name", "street", "city")
    @classmethod
    def trim_whitespace(cls, v: str) -> str:
        """Trim whitespace from string fields"""
        return v.strip()

    model_config = {
        "extra": "forbid",  # Reject extra fields for safety
        "validate_assignment": True,
    }
