"""Select the public wire id for an execution operation."""

from __future__ import annotations

from ..adapters.execution_registry import list_applicable_wires
from ..errors import PortoError, PortoErrorCode


def select_wire(
    *,
    provider_id: str,
    operation: str,
    pin: str | None = None,
    data_path: str | None = None,
) -> str:
    """Pick the wire for this call: explicit pin, sole applicable, or fail closed."""
    provider = provider_id.strip().lower()
    applicable = list_applicable_wires(provider, operation, data_path)
    token = (pin or "").strip().lower() or None
    if token:
        if token not in applicable:
            raise PortoError(
                f"{operation} is not supported for wire {token!r}",
                PortoErrorCode.PORTO_CAPABILITY_UNSUPPORTED,
                status_code=501,
                details={
                    "capability": operation,
                    "provider_id": provider,
                    "wire": token,
                },
                provider=provider,
                wire=token,
                retryable=False,
            )
        return token
    if len(applicable) == 1:
        return applicable[0]
    raise PortoError(
        f"{operation} is not supported for provider {provider!r}",
        PortoErrorCode.PORTO_CAPABILITY_UNSUPPORTED,
        status_code=501,
        details={"capability": operation, "provider_id": provider},
        provider=provider,
        retryable=False,
    )
