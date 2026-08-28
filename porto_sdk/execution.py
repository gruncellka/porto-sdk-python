"""
Execution types — Porto (resolved decision) vs PortoMark (provider result).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, overload

from pydantic import BaseModel, Field, field_validator

from .errors.domains.data import raise_data_invalid
from .types import Address, MarkRequest

if TYPE_CHECKING:
    from .data.entities.products import PortoProduct
    from .services.porto_resolver import Porto

MarkType = Literal["stamp", "label"]
TrackingMode = Literal["none", "optional", "included"]
MarkOutputMime = Literal["image/png", "application/pdf"]

DEFAULT_MARK_OUTPUT_MIME: MarkOutputMime = "image/png"


def optional_wire_id(value: str | None) -> str | None:
    """Empty/blank wire ids are absent — never stored as \"\"."""
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def utc_now_iso() -> str:
    """UTC timestamp in the same shape as JS ``Date.toISOString()``."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ExecutionParameters(BaseModel):
    """How this call runs — transport/correlation only.

    ``request_id`` is an optional correlation token for provider wires (e.g. X-Request-ID).
    SDK does not persist idempotency keys.
    """

    request_id: str | None = None
    idempotency_key: str | None = None
    output_mime: MarkOutputMime = DEFAULT_MARK_OUTPUT_MIME
    credentials: dict[str, str] | None = None
    wire: str | None = None

    model_config = {"extra": "forbid"}


class PortoMarkRequest(BaseModel):
    """Public mark extras on a frozen Porto. Identity fields live on ``porto``."""

    porto: Porto
    sender: Address | None = None
    recipient: Address | None = None
    idempotency: str | None = None
    mime: MarkOutputMime | None = None

    model_config = {"extra": "forbid", "arbitrary_types_allowed": True}


class PortoMark(BaseModel):
    """Normalized provider mark-execution result."""

    id: str
    content: str = Field(description="Download URL or inline payload reference")
    content_type: MarkOutputMime
    external_id: str | None = None
    tracking_number: str | None = None
    amount: int
    currency: str = "EUR"
    provider: str
    wire: str
    generated_at: str

    model_config = {"extra": "forbid"}

    @field_validator("content")
    @classmethod
    def _content_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must be non-empty")
        return value

    @field_validator("amount")
    @classmethod
    def _amount_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("amount must be >= 0")
        return value


def build_porto_mark(
    *,
    provider: str,
    wire: str,
    content: str,
    content_type: MarkOutputMime,
    amount: int,
    currency: str = "EUR",
    external_id: str | None = None,
    tracking_number: str | None = None,
    generated_at: str | None = None,
) -> PortoMark:
    """Mint a PortoMark. Adapters must call ProviderBoundMarkFactory.new_mark."""
    return PortoMark(
        id=str(uuid.uuid4()),
        content=content,
        content_type=content_type,
        external_id=optional_wire_id(external_id),
        tracking_number=optional_wire_id(tracking_number),
        amount=amount,
        currency=currency,
        provider=provider,
        wire=wire,
        generated_at=generated_at or utc_now_iso(),
    )


class ProviderBoundMarkFactory:
    """Adapter mixin: provider is closed over; callers cannot set id or provider."""

    provider_id: str
    wire_id: str

    def new_mark(
        self,
        *,
        content: str,
        content_type: MarkOutputMime,
        amount: int,
        currency: str = "EUR",
        external_id: str | None = None,
        tracking_number: str | None = None,
        generated_at: str | None = None,
    ) -> PortoMark:
        return build_porto_mark(
            provider=self.provider_id,
            wire=self.wire_id,
            content=content,
            content_type=content_type,
            amount=amount,
            currency=currency,
            external_id=external_id,
            tracking_number=tracking_number,
            generated_at=generated_at,
        )


class MarkExecution(BaseModel):
    """Prepared mark-execution carrier (prepare → execute).

    Opaque prepare result: no commerce identity, status, or persistence.
    ``porto`` is the frozen resolved identity; ``request`` is the adapter DTO.
    """

    porto: Porto | None = None
    request: MarkRequest
    pre_calculated_price: int | None = None
    mark_profile_id: str | None = None
    allowed_mime_types: list[str] = Field(default_factory=list)
    zone_id: str | None = None
    product_id: str | None = None
    wire_code: int | str | None = None
    mark_type: MarkType | None = None
    tracking: TrackingMode | None = None
    resolved_product: PortoProduct | None = Field(
        default=None,
        exclude=True,
        description="PortoProduct from prepare; not re-resolved at post",
    )

    model_config = {"extra": "forbid", "arbitrary_types_allowed": True}


@overload
def parse_mark_type(value: str | None, *, allow_none: Literal[True]) -> MarkType | None: ...
@overload
def parse_mark_type(value: str | None, *, allow_none: Literal[False] = False) -> MarkType: ...
def parse_mark_type(value: str | None, *, allow_none: bool = False) -> MarkType | None:
    if value is None or str(value).strip() == "":
        if allow_none:
            return None
        raise_data_invalid("Missing mark type")
        raise AssertionError("unreachable")
    token = str(value).strip()
    if token in ("stamp", "label"):
        return token  # type: ignore[return-value]
    raise_data_invalid(f"Unknown mark type: {value!r}", details={"mark_type": value})
    raise AssertionError("unreachable")


@overload
def parse_tracking_mode(value: str | None, *, allow_none: Literal[True]) -> TrackingMode | None: ...
@overload
def parse_tracking_mode(
    value: str | None, *, allow_none: Literal[False] = False
) -> TrackingMode: ...
def parse_tracking_mode(value: str | None, *, allow_none: bool = False) -> TrackingMode | None:
    if value is None or str(value).strip() == "":
        if allow_none:
            return None
        raise_data_invalid("Missing tracking mode")
        raise AssertionError("unreachable")
    token = str(value).strip()
    if token in ("none", "optional", "included"):
        return token  # type: ignore[return-value]
    raise_data_invalid(f"Unknown tracking mode: {value!r}", details={"tracking": value})
    raise AssertionError("unreachable")


def normalize_mark_type(value: str | None) -> MarkType:
    parsed = parse_mark_type(value, allow_none=False)
    assert parsed is not None
    return parsed


def normalize_tracking_mode(value: str | None) -> TrackingMode:
    parsed = parse_tracking_mode(value, allow_none=False)
    assert parsed is not None
    return parsed


def validate_output_mime(
    requested: str,
    allowed: list[str],
    *,
    default: str = DEFAULT_MARK_OUTPUT_MIME,
) -> str:
    if requested in allowed:
        return requested
    if default in allowed:
        return default
    if allowed:
        return allowed[0]
    return requested


def mark_wire(mark: PortoMark) -> str:
    """Wire id recorded on the executed PortoMark."""
    return (mark.wire or "").strip().lower()
