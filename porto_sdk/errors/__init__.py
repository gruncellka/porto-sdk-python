"""
Unified error handling for Porto SDK

Provider vs wire:
- provider: postal operator (aligned with porto-data)
- wire: backend/API adapter identifier for a provider
"""

from porto_sdk.errors.codes import PortoErrorCode
from porto_sdk.errors.exceptions import (
    AuthenticationError,
    ConfigurationError,
    DataError,
    PortoError,
    ProviderError,
    TransportError,
    ValidationError,
)
from porto_sdk.errors.models import map_provider_error, redact_sensitive_fields

__all__ = [
    "AuthenticationError",
    "ConfigurationError",
    "DataError",
    "PortoError",
    "PortoErrorCode",
    "ProviderError",
    "TransportError",
    "ValidationError",
    "map_provider_error",
    "redact_sensitive_fields",
]
