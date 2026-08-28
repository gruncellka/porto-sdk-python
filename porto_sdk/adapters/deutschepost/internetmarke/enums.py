"""
Internetmarke Adapter Enums

Enums for Internetmarke API integration.
"""

from enum import Enum


class InternetmarkeVendorErrorPattern(str, Enum):
    """Vendor error code patterns for matching"""

    AUTH = "AUTH"
    LOGIN = "LOGIN"
    INSUFFICIENT = "INSUFFICIENT"
    FUNDS = "FUNDS"
    WALLET = "WALLET"
    BALANCE = "BALANCE"
    PRODUCT = "PRODUCT"
    INVALID_PRODUCT = "INVALID_PRODUCT"
    RATE_LIMIT = "RATE_LIMIT"
    TOO_MANY = "TOO_MANY"


class InternetmarkeRetryableErrorCode(str, Enum):
    """Retryable vendor error codes"""

    TIMEOUT = "TIMEOUT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    RATE_LIMIT = "RATE_LIMIT"
