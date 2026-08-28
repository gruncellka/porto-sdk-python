"""Execution adapter placeholder when operator has no wired execution."""

from __future__ import annotations

from ..errors import PortoError, PortoErrorCode
from ..execution import ExecutionParameters, PortoMark
from ..types import MarkRequest
from .protocols.execution import Balance


class UnavailableExecutionAdapter:
    """No execution wire for this operator — fails clearly, no IM impersonation."""

    def __init__(self, provider_id: str, wire_id: str | None = None) -> None:
        self._provider_id = provider_id.strip().lower()
        self._wire_id = wire_id or "none"

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def wire_id(self) -> str:
        return self._wire_id

    async def mark(
        self,
        request: MarkRequest,
        resolved_product=None,
        execution: ExecutionParameters | None = None,
    ) -> PortoMark:
        raise self._unsupported("mark")

    async def balance(self, execution: ExecutionParameters | None = None) -> Balance:
        raise self._unsupported("wallet")

    async def health(self):
        from ..states import CapabilityState, HealthStatus

        return HealthStatus(
            state=CapabilityState.UNAVAILABLE,
            detail=f"no execution wire for {self._provider_id}",
        )

    def normalize_document(self, payload: bytes) -> bytes:
        return payload

    def _unsupported(self, capability: str) -> PortoError:
        return PortoError(
            f"{capability} is not supported for provider {self._provider_id!r}",
            PortoErrorCode.PORTO_CAPABILITY_UNSUPPORTED,
            status_code=501,
            details={
                "capability": capability,
                "provider_id": self._provider_id,
                "wire": self._wire_id,
            },
            provider=self._provider_id,
            wire=self._wire_id,
            retryable=False,
        )
