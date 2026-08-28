"""
Internetmarke Adapter Utilities

Utility functions for address normalization, product mapping, and error handling.
Uses official DHL REST API format: addressLine1, country (3-letter), productCode (int).
"""

from collections.abc import Callable
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from ....errors import PortoError, PortoErrorCode
from ....types import Address
from .enums import (
    InternetmarkeRetryableErrorCode,
    InternetmarkeVendorErrorPattern,
)
from .schemas import InternetmarkeAddressSchema


def normalize_address(
    address: Address,
    *,
    resolve_country_code_3: Callable[[str], str],
) -> dict[str, str]:
    """
    Normalize address to DHL INTERNETMARKE format (AppShoppingCartPDFRequest).
    Returns: {name, additionalName?, addressLine1, addressLine2?, postalCode, city, country}
    country is ISO 3166-1 alpha-3 (e.g. DEU) from jurisdictions.country_code_3.
    """
    try:
        validated = InternetmarkeAddressSchema(
            name=address.name,
            street=address.street,
            houseNumber=address.house_number,
            postalCode=address.postal_code,
            city=address.locality,
            countryCode=address.country_code,
            regionCode=address.region_code,
        )
    except PydanticValidationError as e:
        raise PortoError(
            f"Invalid address format: {e}",
            PortoErrorCode.PORTO_MARK_INVALID,
            status_code=400,
            details={"validation_errors": e.errors(), "address": address.model_dump()},
            provider="deutschepost",
            wire="internetmarke",
            retryable=False,
        ) from e

    addr = validated.model_dump(exclude_none=True)
    street = addr.get("street", "")
    house = addr.get("houseNumber", "")
    address_line1 = f"{street} {house}".strip()
    alpha2 = str(addr.get("countryCode") or "").strip().upper()
    country = resolve_country_code_3(alpha2)

    result: dict[str, str] = {
        "name": addr.get("name", ""),
        "addressLine1": address_line1,
        "postalCode": addr.get("postalCode", ""),
        "city": addr.get("city", ""),
        "country": country,
    }
    if addr.get("regionCode"):
        result["additionalName"] = addr["regionCode"]
    return result


def require_internetmarke_product_code(wire_code: int | str | None) -> int:
    """Validate resolved graph wire code for DHL Internetmarke productCode."""
    if isinstance(wire_code, int) and wire_code > 0:
        return wire_code
    if isinstance(wire_code, str) and wire_code.isdigit():
        return int(wire_code)
    raise PortoError(
        "Internetmarke wire_code missing or invalid. "
        "Ensure graph.edges.wire.internetmarke defines the product/zone/service combination.",
        PortoErrorCode.PORTO_MARK_FAILED,
        status_code=400,
        details={
            "wire_code": wire_code,
        },
        provider="deutschepost",
        wire="internetmarke",
        retryable=False,
    )


def extract_internetmarke_vendor_error_code(err_data: dict[str, Any] | None) -> str | None:
    """
    DHL Internetmarke shopping-cart / directCheckout errors use RFC7807-style JSON:
    { "statusCode": "400", "title": "walletBalanceNotEnough", "description": "<PortokasseID>" }.
    Some responses instead carry `code`, `errorCode`, or `message`, or nest the
    whole error object under `error`, so all of those shapes are probed.
    """
    if not err_data:
        return None
    for key in ("title", "code", "errorCode", "message"):
        value = err_data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    nested = err_data.get("error")
    if isinstance(nested, dict):
        return extract_internetmarke_vendor_error_code(nested)
    if isinstance(nested, str) and nested.strip():
        return nested.strip()
    return None


def _normalized_vendor_token(vendor_code: str) -> str:
    return vendor_code.upper().replace("_", "").replace("-", "")


def map_internetmarke_error_code(vendor_code: str | None, http_status: int) -> PortoErrorCode:
    """
    Map INTERNETMARKE vendor error codes to SDK error codes.
    Preserves vendor code in error details for compliance.
    """
    if not vendor_code:
        if http_status == 401:
            return PortoErrorCode.PORTO_AUTH_FAILED
        elif http_status == 403:
            return PortoErrorCode.PORTO_AUTH_DENIED
        elif http_status == 429:
            return PortoErrorCode.PORTO_NETWORK_RATE_LIMITED
        elif http_status >= 500:
            return PortoErrorCode.PORTO_NETWORK_UNAVAILABLE
        else:
            return PortoErrorCode.PORTO_MARK_FAILED

    vendor_code_upper = vendor_code.upper()

    if (
        InternetmarkeVendorErrorPattern.AUTH.value in vendor_code_upper
        or InternetmarkeVendorErrorPattern.LOGIN.value in vendor_code_upper
    ):
        return PortoErrorCode.PORTO_AUTH_FAILED

    normalized = _normalized_vendor_token(vendor_code_upper)
    if (
        InternetmarkeVendorErrorPattern.INSUFFICIENT.value in vendor_code_upper
        or InternetmarkeVendorErrorPattern.FUNDS.value in vendor_code_upper
        or (
            InternetmarkeVendorErrorPattern.WALLET.value in vendor_code_upper
            and InternetmarkeVendorErrorPattern.BALANCE.value in vendor_code_upper
        )
        or "WALLETBALANCE" in normalized
        or "NOTENOUGH" in normalized
    ):
        return PortoErrorCode.PORTO_WALLET_INSUFFICIENT

    if (
        InternetmarkeVendorErrorPattern.PRODUCT.value in vendor_code_upper
        or InternetmarkeVendorErrorPattern.INVALID_PRODUCT.value in vendor_code_upper
    ):
        return PortoErrorCode.PORTO_MARK_FAILED

    # Check for rate limit errors
    if (
        InternetmarkeVendorErrorPattern.RATE_LIMIT.value in vendor_code_upper
        or InternetmarkeVendorErrorPattern.TOO_MANY.value in vendor_code_upper
    ):
        return PortoErrorCode.PORTO_NETWORK_RATE_LIMITED

    return PortoErrorCode.PORTO_MARK_FAILED


_NEVER_RETRYABLE_CODES = {
    PortoErrorCode.PORTO_WALLET_INSUFFICIENT,
    PortoErrorCode.PORTO_AUTH_FAILED,
    PortoErrorCode.PORTO_AUTH_DENIED,
    PortoErrorCode.PORTO_LINKAGE_PENDING,
}


def is_retryable_error(http_status: int, vendor_code: str | None) -> bool:
    """Wallet/auth are never retryable. 5xx and 429 are retryable otherwise."""
    mapped = map_internetmarke_error_code(vendor_code, http_status)
    if mapped in _NEVER_RETRYABLE_CODES:
        return False
    if http_status >= 500 or http_status == 429:
        return True
    if vendor_code:
        vendor_code_upper = vendor_code.upper()
        retryable_codes = [
            InternetmarkeRetryableErrorCode.TIMEOUT.value,
            InternetmarkeRetryableErrorCode.SERVICE_UNAVAILABLE.value,
            InternetmarkeRetryableErrorCode.RATE_LIMIT.value,
        ]
        if any(code in vendor_code_upper for code in retryable_codes):
            return True
    return False


def parse_error_response(response: Any) -> dict[str, Any]:
    """
    Parse error response from INTERNETMARKE API.
    Supports both JSON and XML formats.
    """
    try:
        # Try JSON first
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type or "text/json" in content_type:
            return response.json()  # type: ignore[no-any-return]
        elif "application/xml" in content_type or "text/xml" in content_type:
            # XML parsing - basic implementation
            import xml.etree.ElementTree as ET

            try:
                root = ET.fromstring(response.text)
                error_data = {}
                for child in root:
                    error_data[child.tag] = child.text
                return error_data
            except ET.ParseError:
                return {"message": response.text, "code": None}
        else:
            # Fallback: try to parse as JSON anyway
            try:
                return response.json()  # type: ignore[no-any-return]
            except Exception:
                return {"message": response.text, "code": None}
    except Exception:
        return {
            "message": f"Failed to parse error response: {response.text[:200]}",
            "code": None,
            "raw_response": response.text[:500],  # First 500 chars for debugging
        }


def parse_wallet_balance_cents(response: dict[str, Any] | None) -> int | None:
    """DHL returns remaining Portokasse balance as walletBallance (provider typo) in cents."""
    if not response:
        return None
    for key in ("walletBallance", "walletBalance"):
        raw = response.get(key)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
    return None


def parse_response(response: Any) -> dict[str, Any]:
    """
    Parse successful response from INTERNETMARKE API.
    Supports both JSON and XML formats.
    """
    content_type = response.headers.get("content-type", "").lower()
    if "application/json" in content_type or "text/json" in content_type:
        return response.json()  # type: ignore[no-any-return]
    elif "application/xml" in content_type or "text/xml" in content_type:
        # XML parsing - basic implementation
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(response.text)
            data = {}
            for child in root:
                data[child.tag] = child.text
            return data
        except ET.ParseError:
            # Fallback to JSON if XML parsing fails
            return response.json()  # type: ignore[no-any-return]
    else:
        # Default to JSON
        return response.json()  # type: ignore[no-any-return]
