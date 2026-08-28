"""
Internetmarke Adapter - Main Facade

Orchestrates authentication and API calls. Does not resolve products or zones.
Credentials are resolved per call and never written onto adapter instance state.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime

from ....adapters.protocols.execution import Balance, ExecutionAdapter
from ....data.loader import PortoProduct
from ....errors import PortoError, PortoErrorCode
from ....execution import (
    ExecutionParameters,
    MarkExecution,
    PortoMark,
    ProviderBoundMarkFactory,
    validate_output_mime,
)
from ....types import MarkRequest, TrackingStatus
from .auth import InternetmarkeAuth
from .checkout import InternetmarkeCheckout
from .document_payload import normalize_document_payload
from .mark_many_policy import require_mark_many_prepared
from .positions import PositionFactory, PositionMark
from .utils import normalize_address, require_internetmarke_product_code

logger = logging.getLogger(__name__)


class InternetmarkeAdapter(ExecutionAdapter, ProviderBoundMarkFactory):
    """Deutsche Post Internetmarke execution adapter."""

    provider_id = "deutschepost"
    wire_id = "internetmarke"

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        username: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str = "https://api-eu.dhl.com/post/de/shipping/im/v1",
        partner_id: str | None = None,
        allowed_mime_types: list[str] | None = None,
        http_client=None,
        country_code_3_lookup: Callable[[str], str] | None = None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.partner_id = partner_id
        self.http_client = http_client
        self.last_many_trace: dict | None = None
        self._country_code_3_lookup = country_code_3_lookup
        self.allowed_mime_types = allowed_mime_types or [
            "image/png",
            "application/pdf",
        ]
        user = email or username
        self._default_user_credentials: dict[str, str] | None
        if user and password:
            self._default_user_credentials = {"username": user, "password": password}
        else:
            self._default_user_credentials = None

    def set_country_code_3_lookup(self, lookup: Callable[[str], str]) -> None:
        """Bind jurisdictions.country_code_3 (alpha-2 → alpha-3) from PortoClient loader."""
        self._country_code_3_lookup = lookup

    def _resolve_country_code_3(self, alpha2: str) -> str:
        if self._country_code_3_lookup is None:
            raise PortoError(
                "Internetmarke country_code_3 lookup is not bound; use PortoClient.provider()",
                PortoErrorCode.PORTO_MARK_FAILED,
                status_code=500,
                provider="deutschepost",
                wire="internetmarke",
                retryable=False,
            )
        return self._country_code_3_lookup(alpha2)

    def _credentials_for(self, execution: ExecutionParameters | None) -> dict[str, str]:
        if execution is not None and execution.credentials:
            return dict(execution.credentials)
        if self._default_user_credentials:
            return dict(self._default_user_credentials)
        return {}

    def _auth_for(self, execution: ExecutionParameters | None) -> InternetmarkeAuth:
        creds = self._credentials_for(execution)
        username = creds.get("username") or creds.get("email")
        password = creds.get("password")
        api_key = creds.get("dhl_api_key") or self.api_key
        api_secret = creds.get("dhl_api_secret") or self.api_secret
        partner_id = creds.get("partner_id") or self.partner_id
        if not username or not password or not api_key or not api_secret:
            raise PortoError(
                "Authentication could not be completed because credentials are missing, invalid, or expired.",
                PortoErrorCode.PORTO_AUTH_FAILED,
                status_code=401,
                provider=self.provider_id,
                wire=self.wire_id,
                retryable=False,
            )
        return InternetmarkeAuth(
            email=username,
            password=password,
            api_key=api_key,
            api_secret=api_secret,
            base_url=self.base_url,
            partner_id=partner_id,
            http_client=self.http_client,
        )

    async def mark(
        self,
        request: MarkRequest,
        resolved_product: PortoProduct | None = None,
        execution: ExecutionParameters | None = None,
    ) -> PortoMark:
        if not resolved_product:
            raise PortoError(
                "Resolved product required for mark creation. "
                "Ensure PortoExecution resolves before calling adapter.",
                PortoErrorCode.PORTO_MARK_FAILED,
                status_code=400,
                provider="deutschepost",
                wire="internetmarke",
                details={"reason": "resolved_product_required"},
                retryable=False,
            )

        request_id = (execution.request_id if execution else None) or str(uuid.uuid4())
        recipient_address, sender_address = self._prepare_addresses(request)
        product_code = require_internetmarke_product_code(request.wire_code)
        franking_zone = request.zone or "domestic"
        self._validate_request(product_code, franking_zone, request)

        mark_type = getattr(resolved_product, "mark_type", None) or "stamp"
        opts = self._bind_execution(
            execution,
            request_id=request_id,
            idempotency_key=request.idempotency_key
            or (execution.idempotency_key if execution else None),
        )
        line = PositionMark(
            product_code=product_code,
            mark_type=mark_type,
            recipient_address=recipient_address,
            sender_address=sender_address,
        )
        factory = PositionFactory()
        checkout = self._checkout_for(execution)
        if opts.output_mime == "application/pdf":
            result = await checkout.pdf(
                positions=[factory.pdf(line)],
                total=request.value,
                execution=opts,
            )
            return self.new_mark(
                content=result.link,
                content_type="application/pdf",
                amount=request.value,
                external_id=result.shop_order_id,
            )
        result = await checkout.png(
            positions=[factory.png(line)],
            total=request.value,
            execution=opts,
        )
        return self.new_mark(
            content=result.link,
            content_type="image/png",
            amount=request.value,
            external_id=result.shop_order_id,
        )

    async def mark_many(
        self,
        prepared: Sequence[MarkExecution],
        execution: ExecutionParameters | None = None,
    ) -> list[PortoMark]:
        require_mark_many_prepared(prepared)
        request_id = (execution.request_id if execution else None) or str(uuid.uuid4())
        factory = PositionFactory()
        lines: list[PositionMark] = []
        values: list[int] = []
        first_idempotency: str | None = None
        for item in prepared:
            request = item.request
            if first_idempotency is None:
                first_idempotency = request.idempotency_key or (
                    execution.idempotency_key if execution else None
                )
            if not item.resolved_product:
                raise PortoError(
                    "Resolved product required for mark creation. "
                    "Ensure PortoExecution resolves before calling adapter.",
                    PortoErrorCode.PORTO_MARK_FAILED,
                    status_code=400,
                    provider="deutschepost",
                    wire="internetmarke",
                    details={"reason": "resolved_product_required"},
                    retryable=False,
                )
            recipient_address, sender_address = self._prepare_addresses(request)
            product_code = require_internetmarke_product_code(request.wire_code)
            franking_zone = request.zone or "domestic"
            self._validate_request(product_code, franking_zone, request)
            lines.append(
                PositionMark(
                    product_code=product_code,
                    mark_type=item.mark_type
                    or getattr(item.resolved_product, "mark_type", None)
                    or "stamp",
                    recipient_address=recipient_address,
                    sender_address=sender_address,
                )
            )
            values.append(request.value)
        opts = self._bind_execution(
            execution,
            request_id=request_id,
            idempotency_key=first_idempotency,
        )
        checkout = self._checkout_for(execution)
        total = sum(values)
        if opts.output_mime == "application/pdf":
            result = await checkout.pdf(
                positions=[factory.pdf(line) for line in lines],
                total=total,
                execution=opts,
            )
            self.last_many_trace = result.trace()
            return [
                self.new_mark(
                    content=result.link,
                    content_type="application/pdf",
                    amount=value,
                    external_id=result.shop_order_id,
                )
                for value in values
            ]
        result = await checkout.png(
            positions=[factory.png(line) for line in lines],
            total=total,
            execution=opts,
        )
        self.last_many_trace = result.trace()
        return [
            self.new_mark(
                content=result.link,
                content_type="image/png",
                amount=value,
                external_id=result.shop_order_id,
            )
            for value in values
        ]

    def _bind_execution(
        self,
        execution: ExecutionParameters | None,
        *,
        request_id: str,
        idempotency_key: str | None,
    ) -> ExecutionParameters:
        opts = execution or ExecutionParameters()
        return opts.model_copy(
            update={
                "request_id": request_id,
                "idempotency_key": idempotency_key or opts.idempotency_key,
                "output_mime": validate_output_mime(
                    opts.output_mime,
                    self.allowed_mime_types,
                ),
            }
        )

    def _checkout_for(self, execution: ExecutionParameters | None) -> InternetmarkeCheckout:
        return InternetmarkeCheckout(
            self._auth_for(execution),
            base_url=self.base_url,
            http_client=self.http_client,
        )

    def _prepare_addresses(
        self, request: MarkRequest
    ) -> tuple[dict[str, str] | None, dict[str, str] | None]:
        recipient_address = None
        sender_address = None
        if request.destination:
            recipient_address = normalize_address(
                request.destination,
                resolve_country_code_3=self._resolve_country_code_3,
            )
        if request.origin:
            sender_address = normalize_address(
                request.origin,
                resolve_country_code_3=self._resolve_country_code_3,
            )
        return recipient_address, sender_address

    def _validate_request(
        self,
        product_code: int,
        franking_zone: str,
        request: MarkRequest,
    ) -> None:
        if product_code is None or product_code <= 0:
            raise PortoError(
                "Product code is required",
                PortoErrorCode.PORTO_MARK_FAILED,
                status_code=400,
                provider="deutschepost",
                wire="internetmarke",
                details={"reason": "invalid_product_code"},
                retryable=False,
            )
        if not franking_zone:
            raise PortoError(
                "Franking zone is required",
                PortoErrorCode.PORTO_PRODUCT_NOT_FOUND,
                status_code=400,
                provider="deutschepost",
                wire="internetmarke",
                retryable=False,
            )
        if request.value <= 0:
            raise PortoError(
                "Total amount must be greater than 0",
                PortoErrorCode.PORTO_MARK_FAILED,
                status_code=400,
                provider="deutschepost",
                wire="internetmarke",
                retryable=False,
            )

    async def balance(self, execution: ExecutionParameters | None = None) -> Balance:
        auth = self._auth_for(execution)
        await auth.authenticate()
        balance_cents = auth.get_wallet_balance_cents()
        if balance_cents is None:
            raise PortoError(
                "Wallet balance not returned by provider",
                PortoErrorCode.PORTO_MARK_FAILED,
                status_code=502,
                provider=self.provider_id,
                wire=self.wire_id,
                retryable=True,
            )
        return Balance(
            balance_cents=balance_cents,
            currency="EUR",
            provider=self.provider_id,
            wire=self.wire_id,
            account_ref=None,
            as_of=datetime.now(),
            billing_model="prepaid",
        )

    async def track_stamp(self, tracking_number: str) -> TrackingStatus:
        raise PortoError(
            "Tracking not available for INTERNETMARKE stamps",
            PortoErrorCode.PORTO_TRACKING_UNSUPPORTED,
            provider="deutschepost",
            wire="internetmarke",
            details={
                "provider_id": "deutschepost",
                "wire": "internetmarke",
                "tracking_kind": "stamp",
                "tracking_number": tracking_number,
            },
            retryable=False,
        )

    def normalize_document(self, payload: bytes) -> bytes:
        return normalize_document_payload(payload)

    async def health(self):
        from ....states import CapabilityState, HealthStatus

        return HealthStatus(state=CapabilityState.READY)

    async def close(self) -> None:
        return
