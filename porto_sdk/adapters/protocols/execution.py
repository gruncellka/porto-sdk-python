"""
Execution adapter protocol — mark execution and prepaid wallet read.

Tracking is not part of this protocol; adapters may expose tracking internally.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ...data.loader import PortoProduct
    from ...execution import ExecutionParameters, PortoMark
    from ...states import HealthStatus
    from ...types import MarkRequest


class Balance:
    """Prepaid wallet snapshot from a provider that supports wallet."""

    balance_cents: int
    currency: str
    provider: str
    wire: str
    account_ref: str | None
    as_of: datetime
    billing_model: Literal["prepaid"]

    def __init__(
        self,
        *,
        balance_cents: int,
        currency: str,
        provider: str,
        wire: str,
        account_ref: str | None,
        as_of: datetime,
        billing_model: Literal["prepaid"] = "prepaid",
    ) -> None:
        self.balance_cents = balance_cents
        self.currency = currency
        self.provider = provider
        self.wire = wire
        self.account_ref = account_ref
        self.as_of = as_of
        self.billing_model = billing_model


@runtime_checkable
class ExecutionAdapter(Protocol):
    """Provider wire for synchronous mark execution and optional wallet read."""

    @property
    def provider_id(self) -> str: ...

    @property
    def wire_id(self) -> str: ...

    async def mark(
        self,
        request: MarkRequest,
        resolved_product: PortoProduct | None = None,
        execution: ExecutionParameters | None = None,
    ) -> PortoMark: ...

    async def balance(self, execution: ExecutionParameters | None = None) -> Balance: ...

    async def health(self) -> HealthStatus: ...

    def normalize_document(self, payload: bytes) -> bytes: ...
