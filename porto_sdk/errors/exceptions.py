"""Porto SDK exception types."""

from __future__ import annotations

from porto_sdk.errors.codes import PortoErrorCode


class PortoError(Exception):
    message: str
    code: PortoErrorCode
    status_code: int | None
    details: dict[str, object] | None
    retryable: bool
    provider: str | None
    wire: str | None
    upstream_code: str | None
    provider_error: object | None

    def __init__(
        self,
        message: str,
        code: PortoErrorCode,
        status_code: int | None = None,
        details: dict[str, object] | None = None,
        retryable: bool = False,
        provider: str | None = None,
        wire: str | None = None,
        upstream_code: str | None = None,
        provider_error: object | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        self.retryable = retryable
        self.provider = provider
        self.wire = wire
        self.upstream_code = upstream_code
        self.provider_error = provider_error

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"


class ValidationError(PortoError):
    """Raised when SDK input/domain validation fails."""


class AuthenticationError(PortoError):
    """Raised when provider authentication fails."""


class TransportError(PortoError):
    """Raised for transport/network/timeout failures."""


class ProviderError(PortoError):
    """Raised for provider-side business/protocol failures."""


class ConfigurationError(PortoError):
    """Raised when SDK configuration is invalid or incomplete."""


class DataError(PortoError):
    """Raised when porto-data cannot be loaded/used correctly."""
