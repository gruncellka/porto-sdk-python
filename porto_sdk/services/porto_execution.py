"""PortoExecution — prepare and execute marks via ExecutionAdapter."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import TYPE_CHECKING, cast, overload

from ..adapters.protocols.execution import ExecutionAdapter
from ..adapters.unavailable_execution import UnavailableExecutionAdapter
from ..data.loader import PortoDataLoader
from ..errors import PortoError, PortoErrorCode
from ..execution import (
    ExecutionParameters,
    MarkExecution,
    PortoMark,
    PortoMarkRequest,
    normalize_mark_type,
    normalize_tracking_mode,
    validate_output_mime,
)
from ..mark_content import fetch_mark_bytes
from ..requires import RECIPIENT, SENDER
from ..services.execution_binding import ExecutionBinding
from ..services.porto_resolver import PortoResolver
from ..services.wire_selection import select_wire
from ..types import Address, MarkRequest, ValidationResult

if TYPE_CHECKING:
    from ..services.validation import LetterValidationService


def _address_invalid_details(result: ValidationResult, country_code: str) -> dict:
    data = result.data or {}
    issues = data.get("form_issues") or []
    first = issues[0] if issues else {}
    details: dict = {"country_code": country_code}
    if data.get("jurisdiction"):
        details["jurisdiction"] = data["jurisdiction"]
    elif country_code:
        details["jurisdiction"] = country_code.upper()
    if first.get("field"):
        details["field"] = first["field"]
    if first.get("code"):
        details["reason"] = first["code"]
    if issues:
        details["form_issues"] = issues
    return details


class PortoExecution:
    def __init__(
        self,
        data_loader: PortoDataLoader,
        adapter: ExecutionAdapter | None = None,
        resolver: PortoResolver | None = None,
        validation: LetterValidationService | None = None,
    ):
        self.data_loader = data_loader
        self._binding = ExecutionBinding(data_loader)
        self._adapter = adapter or UnavailableExecutionAdapter(data_loader.provider_id, "none")
        self._resolver = resolver
        self._validation = validation

    @property
    def adapter(self) -> ExecutionAdapter:
        return self._adapter

    @adapter.setter
    def adapter(self, value: ExecutionAdapter) -> None:
        self._adapter = value

    def set_resolver(self, resolver: PortoResolver) -> None:
        self._resolver = resolver

    def set_validation(self, validation: LetterValidationService) -> None:
        self._validation = validation

    async def _role(
        self,
        address: Address | None,
        *,
        required: bool,
        missing: PortoErrorCode,
        invalid: PortoErrorCode,
        role: str,
    ) -> Address | None:
        if not required:
            return None
        if address is None:
            raise PortoError(
                f"{role} address is required for this resolved Porto",
                missing,
                status_code=400,
                details={"role": role},
                retryable=False,
            )
        if self._validation:
            result = await self._validation.validate_address(address)
            if not result.is_valid:
                raise PortoError(
                    f"Invalid {role} address: {', '.join(result.errors)}",
                    invalid,
                    status_code=400,
                    details=_address_invalid_details(result, address.country_code),
                    retryable=False,
                )
        return address

    async def prepare(self, request: PortoMarkRequest) -> MarkExecution:
        porto = request.porto
        sender = await self._role(
            request.sender,
            required=SENDER in porto.requires,
            missing=PortoErrorCode.PORTO_ADDRESS_SENDER_REQUIRED,
            invalid=PortoErrorCode.PORTO_ADDRESS_SENDER_INVALID,
            role="sender",
        )
        recipient = await self._role(
            request.recipient,
            required=RECIPIENT in porto.requires,
            missing=PortoErrorCode.PORTO_ADDRESS_RECIPIENT_REQUIRED,
            invalid=PortoErrorCode.PORTO_ADDRESS_RECIPIENT_INVALID,
            role="recipient",
        )
        service_ids = list(porto.service_ids)
        binding = self._binding.bind(
            wire=self._adapter.wire_id,
            product_id=porto.product.id,
            zone_id=porto.zone.id,
            service_ids=service_ids or None,
        )
        mark_profile_id = binding.mark_profile_id
        profile = (
            self.data_loader.get_mark_profile(mark_profile_id)
            if mark_profile_id
            else self.data_loader.get_default_mark_profile()
        )
        allowed = list(profile.mime_types) if profile else ["image/png", "application/pdf"]

        total_minor = int(porto.amount)

        adapter_request = MarkRequest(
            destination=recipient,
            origin=sender,
            value=total_minor,
            zone=porto.zone.id,
            idempotency_key=request.idempotency,
            wire_code=binding.wire_code,
        )
        return MarkExecution(
            porto=porto,
            request=adapter_request,
            pre_calculated_price=total_minor,
            mark_profile_id=mark_profile_id or (profile.id if profile else None),
            allowed_mime_types=allowed,
            zone_id=porto.zone.id,
            product_id=porto.product.id,
            wire_code=binding.wire_code,
            mark_type=normalize_mark_type(porto.mark_type),
            tracking=normalize_tracking_mode(getattr(porto.product, "tracking", None)),
            resolved_product=porto.product,
        )

    async def _one(
        self,
        request: PortoMarkRequest,
        execution: ExecutionParameters | None = None,
    ) -> PortoMark:
        opts = execution or ExecutionParameters()
        wire = select_wire(
            provider_id=self.data_loader.provider_id,
            operation="mark",
            pin=opts.wire,
            data_path=str(self.data_loader.data_path),
        )
        if self._adapter.wire_id not in (wire,):
            raise PortoError(
                f"mark is not supported for wire {wire!r}",
                PortoErrorCode.PORTO_CAPABILITY_UNSUPPORTED,
                status_code=501,
                details={
                    "capability": "mark",
                    "provider_id": self.data_loader.provider_id,
                    "wire": wire,
                },
                provider=self.data_loader.provider_id,
                wire=wire,
                retryable=False,
            )
        prepared = await self.prepare(request)
        if request.mime:
            opts = opts.model_copy(update={"output_mime": request.mime})
        if request.idempotency and not opts.idempotency_key:
            opts = opts.model_copy(update={"idempotency_key": request.idempotency})
        return await self.execute(prepared, 0, opts)

    async def _many(
        self,
        requests: Sequence[PortoMarkRequest],
        execution: ExecutionParameters | None = None,
    ) -> list[PortoMark]:
        items = list(requests)
        if not items:
            raise PortoError(
                "mark(many) requires at least one request",
                PortoErrorCode.PORTO_MARK_INVALID,
                status_code=400,
                retryable=False,
            )
        opts = execution or ExecutionParameters()
        wire = select_wire(
            provider_id=self.data_loader.provider_id,
            operation="mark",
            pin=opts.wire,
            data_path=str(self.data_loader.data_path),
        )
        if self._adapter.wire_id not in (wire,):
            raise PortoError(
                f"mark is not supported for wire {wire!r}",
                PortoErrorCode.PORTO_CAPABILITY_UNSUPPORTED,
                status_code=501,
                details={
                    "capability": "mark",
                    "provider_id": self.data_loader.provider_id,
                    "wire": wire,
                },
                provider=self.data_loader.provider_id,
                wire=wire,
                retryable=False,
            )
        prepared = [await self.prepare(item) for item in items]
        mark_many = getattr(self._adapter, "mark_many", None)
        if callable(mark_many):
            return cast(list[PortoMark], await mark_many(prepared, opts))
        return [await self.execute(row, 0, opts) for row in prepared]

    @overload
    async def mark(
        self,
        request: PortoMarkRequest,
        execution: ExecutionParameters | None = None,
    ) -> PortoMark: ...

    @overload
    async def mark(
        self,
        request: Sequence[PortoMarkRequest],
        execution: ExecutionParameters | None = None,
    ) -> list[PortoMark]: ...

    async def mark(
        self,
        request: PortoMarkRequest | Sequence[PortoMarkRequest],
        execution: ExecutionParameters | None = None,
    ) -> PortoMark | list[PortoMark]:
        if isinstance(request, Sequence) and not isinstance(request, (str, bytes)):
            return await self._many(request, execution)
        return await self._one(request, execution)

    async def execute(
        self,
        prepared: MarkExecution,
        weight: int,
        execution: ExecutionParameters | None = None,
    ) -> PortoMark:
        del weight
        resolved_product = prepared.resolved_product
        if resolved_product is None:
            raise PortoError(
                "MarkExecution missing resolved_product; call prepare first",
                PortoErrorCode.PORTO_PRODUCT_NOT_FOUND,
                status_code=422,
                retryable=False,
            )
        opts = execution or ExecutionParameters()
        opts = opts.model_copy(
            update={
                "output_mime": validate_output_mime(
                    opts.output_mime,
                    prepared.allowed_mime_types,
                ),
            }
        )
        return await self._adapter.mark(
            prepared.request,
            resolved_product=resolved_product,
            execution=opts,
        )

    async def bytes(
        self,
        mark: PortoMark,
        *,
        retries: int | None = None,
        timeout: timedelta | float | None = None,
    ) -> bytes:
        """Download and normalize mark document bytes (retry-safe; no re-execute)."""
        kwargs: dict = {}
        if retries is not None:
            kwargs["retries"] = retries
        if timeout is not None:
            kwargs["timeout"] = timeout
        normalize = getattr(self._adapter, "normalize_document", None)
        if normalize is not None:
            kwargs["normalize"] = normalize
        return await fetch_mark_bytes(mark, **kwargs)
