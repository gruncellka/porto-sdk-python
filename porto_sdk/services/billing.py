"""
Billing service — prepaid wallet read (capability-gated).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..adapters.protocols.execution import Balance, ExecutionAdapter
from ..errors import PortoError, PortoErrorCode
from ..execution import ExecutionParameters
from ..services.wire_selection import select_wire

if TYPE_CHECKING:
    from ..client import PortoClient


class BillingService:
    def __init__(
        self,
        client: PortoClient,
        *,
        provider_id: str | None = None,
        wires: dict | None = None,
        adapter: ExecutionAdapter | None = None,
    ) -> None:
        self._client = client
        self._provider_id = provider_id
        self._wires = wires
        self._adapter = adapter

    def _provider(self) -> str:
        return self._provider_id or self._client._normalized.default_provider

    def _data_path(self) -> str | None:
        return self._client.config.data

    def _execution_adapter(self) -> ExecutionAdapter:
        if self._adapter is not None:
            return self._adapter
        from ..adapters.execution_registry import get_execution_adapter

        return get_execution_adapter(
            self._provider(),
            self._wires,
            data_path=self._data_path(),
        )

    async def balance(self, execution: ExecutionParameters | None = None) -> Balance:
        provider = self._provider()
        pin = execution.wire if execution else None
        wire = select_wire(
            provider_id=provider,
            operation="wallet",
            pin=pin,
            data_path=self._data_path(),
        )
        adapter = self._execution_adapter()
        if adapter.wire_id != wire:
            raise PortoError(
                f"wallet is not supported for wire {wire!r}",
                PortoErrorCode.PORTO_CAPABILITY_UNSUPPORTED,
                status_code=501,
                details={"capability": "wallet", "provider_id": provider, "wire": wire},
                provider=provider,
                wire=wire,
                retryable=False,
            )
        return await adapter.balance(execution)
