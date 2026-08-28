"""ServiceKind / FeatureKind — projection of porto-data kinds.schema.json."""

from __future__ import annotations

from typing import Literal, get_args

from porto_sdk.errors.domains.data import raise_data_invalid

ServiceKind = Literal[
    "registered",
    "registered_return_receipt",
    "tracking",
    "insurance",
    "return_receipt",
    "thickness",
    "acceptance_proof",
    "delivery_proof",
]
FeatureKind = Literal[
    "tracking",
    "acceptance_proof",
    "recipient_signature",
    "return_receipt",
    "delivery_proof",
    "thickness",
]

SERVICE_KINDS: frozenset[str] = frozenset(get_args(ServiceKind))
FEATURE_KINDS: frozenset[str] = frozenset(get_args(FeatureKind))


def is_service_kind(value: object) -> bool:
    return str(value or "").strip() in SERVICE_KINDS


def is_feature_kind(value: object) -> bool:
    return str(value or "").strip() in FEATURE_KINDS


def parse_service_kind(value: object, *, path: str | None = None) -> ServiceKind:
    token = str(value or "").strip()
    if token in SERVICE_KINDS:
        return token  # type: ignore[return-value]
    raise_data_invalid(
        f"Unknown service kind: {value!r}",
        path=path,
        details={"kind": value},
    )
    raise AssertionError("unreachable")


def parse_feature_kind(value: object, *, path: str | None = None) -> FeatureKind:
    token = str(value or "").strip()
    if token in FEATURE_KINDS:
        return token  # type: ignore[return-value]
    raise_data_invalid(
        f"Unknown feature kind: {value!r}",
        path=path,
        details={"kind": value},
    )
    raise AssertionError("unreachable")
