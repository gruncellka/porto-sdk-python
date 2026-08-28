"""Map Internetmarke HTTP failures to PortoError."""

from __future__ import annotations

from typing import Any, Mapping

from ....errors import PortoError, PortoErrorCode
from .client import HttpJsonResult
from .utils import (
    extract_internetmarke_vendor_error_code,
    is_retryable_error,
    map_internetmarke_error_code,
)

_PROVIDER = "deutschepost"
_WIRE = "internetmarke"


class InternetmarkeErrorMapper:
    def network(self, exc: BaseException, *, request_id: str) -> PortoError:
        return PortoError(
            f"INTERNETMARKE REST network error: {exc!s}",
            PortoErrorCode.PORTO_NETWORK_UNAVAILABLE,
            status_code=503,
            details={"error": str(exc), "requestId": request_id},
            provider=_PROVIDER,
            wire=_WIRE,
            retryable=True,
        )

    def raise_if_init_failed(self, result: HttpJsonResult, *, request_id: str) -> None:
        if result.ok:
            return
        err_data = self._payload(result)
        vendor_code = extract_internetmarke_vendor_error_code(err_data)
        raise PortoError(
            f"INTERNETMARKE init shopping cart failed: {err_data.get('message', result.text[:1000])}",
            map_internetmarke_error_code(vendor_code, result.status_code),
            status_code=result.status_code,
            details={"error": err_data, "requestId": request_id},
            provider=_PROVIDER,
            wire=_WIRE,
            upstream_code=vendor_code,
            retryable=is_retryable_error(result.status_code, vendor_code),
        )

    def raise_if_checkout_failed(
        self,
        result: HttpJsonResult,
        *,
        request_id: str,
        product_code: int | None,
        body: Mapping[str, Any],
    ) -> None:
        if result.ok:
            return
        err_data = self._payload(result)
        vendor_code = extract_internetmarke_vendor_error_code(err_data)
        sdk_code = map_internetmarke_error_code(vendor_code, result.status_code)
        details: dict[str, Any] = {
            "error": err_data,
            "requestId": request_id,
            "productCode": product_code,
            "requestBody": dict(body),
            "required_cents": body.get("total"),
            "wallet_account_id": err_data.get("description"),
            "upstream_title": vendor_code,
        }
        if sdk_code == PortoErrorCode.PORTO_WALLET_INSUFFICIENT:
            required_cents = body.get("total")
            wallet_account_id = err_data.get("description")
            message = (
                "Postage wallet balance too low"
                f"{f' (need {required_cents} ct)' if isinstance(required_cents, int) else ''}"
                f"{f' for {wallet_account_id}' if isinstance(wallet_account_id, str) else ''}"
            )
        else:
            message = f"Mark execution failed: {err_data.get('message', result.text[:1000])}"
        raise PortoError(
            message,
            sdk_code,
            status_code=result.status_code,
            details=details,
            provider=_PROVIDER,
            wire=_WIRE,
            upstream_code=vendor_code,
            retryable=is_retryable_error(result.status_code, vendor_code),
        )

    def _payload(self, result: HttpJsonResult) -> dict[str, Any]:
        data = result.json_data
        if isinstance(data, dict):
            return data
        return {"message": result.text[:1000]}
