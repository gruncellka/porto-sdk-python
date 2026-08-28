# GENERATED from porto_features/errors.json — do not edit.
# Run: make sync-error-bindings

from enum import Enum


class PortoErrorCode(str, Enum):
    PORTO_AUTH_FAILED = (
        "PORTO_AUTH_FAILED"  # auth: Authentication could not be completed because credentials are missing, invalid, or expired.
    )
    PORTO_AUTH_DENIED = (
        "PORTO_AUTH_DENIED"  # auth: Authentication succeeded, but the account or application is not permitted to perform the requested operation.
    )
    PORTO_LINKAGE_PENDING = (
        "PORTO_LINKAGE_PENDING"  # auth: Provider account linkage is awaiting approval.
    )
    PORTO_WALLET_INSUFFICIENT = (
        "PORTO_WALLET_INSUFFICIENT"  # wallet: Prepaid wallet balance is too low for mark execution.
    )
    PORTO_TOO_HEAVY = "PORTO_TOO_HEAVY"  # resolution: Weight exceeds the product or tier maximum.
    PORTO_DESTINATION_INVALID = (
        "PORTO_DESTINATION_INVALID"  # destination: Destination country or zone is unknown or invalid.
    )
    PORTO_PRODUCT_NOT_FOUND = (
        "PORTO_PRODUCT_NOT_FOUND"  # product: No product matches the destination zone and weight tier.
    )
    PORTO_PRODUCT_AMBIGUOUS = (
        "PORTO_PRODUCT_AMBIGUOUS"  # product: Multiple products match; specify which one.
    )
    PORTO_PRICE_NOT_FOUND = (
        "PORTO_PRICE_NOT_FOUND"  # price: No price found for the selected product, zone, and weight tier.
    )
    PORTO_MARK_FAILED = "PORTO_MARK_FAILED"  # mark: PortoMark execution failed.
    PORTO_MARK_INVALID = "PORTO_MARK_INVALID"  # mark: PortoMark request is invalid.
    PORTO_ADDRESS_SENDER_REQUIRED = (
        "PORTO_ADDRESS_SENDER_REQUIRED"  # address: Sender address is required for this resolved Porto.
    )
    PORTO_ADDRESS_SENDER_INVALID = "PORTO_ADDRESS_SENDER_INVALID"  # address: Sender address is invalid.
    PORTO_ADDRESS_RECIPIENT_REQUIRED = (
        "PORTO_ADDRESS_RECIPIENT_REQUIRED"  # address: Recipient address is required for this resolved Porto.
    )
    PORTO_ADDRESS_RECIPIENT_INVALID = "PORTO_ADDRESS_RECIPIENT_INVALID"  # address: Recipient address is invalid.
    PORTO_NETWORK_TIMEOUT = "PORTO_NETWORK_TIMEOUT"  # network: Provider request timed out.
    PORTO_NETWORK_RATE_LIMITED = "PORTO_NETWORK_RATE_LIMITED"  # network: Provider rate limit reached.
    PORTO_NETWORK_UNAVAILABLE = (
        "PORTO_NETWORK_UNAVAILABLE"  # network: Provider endpoint is unavailable or unreachable.
    )
    PORTO_DATA_NOT_FOUND = "PORTO_DATA_NOT_FOUND"  # data: Required postal catalog data is missing.
    PORTO_DATA_INVALID = "PORTO_DATA_INVALID"  # data: Postal catalog data is invalid.
    PORTO_DATA_CORRUPTED = (
        "PORTO_DATA_CORRUPTED"  # data: Postal catalog data failed integrity verification.
    )
    PORTO_DATA_TOO_OLD = "PORTO_DATA_TOO_OLD"  # data: Postal catalog version is too old for this SDK.
    PORTO_DATA_TOO_NEW = (
        "PORTO_DATA_TOO_NEW"  # data: Postal catalog version is too new; upgrade the SDK.
    )
    PORTO_CAPABILITY_UNSUPPORTED = (
        "PORTO_CAPABILITY_UNSUPPORTED"  # capability: This capability is not supported in the current context.
    )
    PORTO_TRACKING_UNSUPPORTED = (
        "PORTO_TRACKING_UNSUPPORTED"  # tracking: Tracking is not supported for this provider or product.
    )
    PORTO_TRACKING_NOT_FOUND = (
        "PORTO_TRACKING_NOT_FOUND"  # tracking: Tracking number is unknown to the carrier.
    )
    PORTO_PROVIDER_NOT_CONFIGURED = (
        "PORTO_PROVIDER_NOT_CONFIGURED"  # provider: Provider is unknown or not configured.
    )
    PORTO_SERVICE_AMBIGUOUS = (
        "PORTO_SERVICE_AMBIGUOUS"  # service: Multiple services match the request; specify which one.
    )
    PORTO_SERVICE_UNSUPPORTED = (
        "PORTO_SERVICE_UNSUPPORTED"  # service: Requested service is not available for this destination or product.
    )
    PORTO_SERVICES_INCOMPATIBLE = (
        "PORTO_SERVICES_INCOMPATIBLE"  # service: Selected postal services cannot be combined.
    )
