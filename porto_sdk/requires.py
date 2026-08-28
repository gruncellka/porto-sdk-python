"""Canonical Porto.requires tokens and set union."""

from __future__ import annotations

from typing import Any, Iterable, Literal, get_args

from porto_sdk.errors.domains.data import raise_data_invalid

Requirement = Literal["ADDRESS_SENDER", "ADDRESS_RECIPIENT"]

SENDER: Requirement = "ADDRESS_SENDER"
RECIPIENT: Requirement = "ADDRESS_RECIPIENT"
ADDRESS = frozenset({SENDER, RECIPIENT})
REQUIREMENTS: frozenset[str] = frozenset(get_args(Requirement))


def parse_requirement(value: object, *, path: str | None = None) -> Requirement:
    token = str(value or "").strip()
    if token in REQUIREMENTS:
        return token  # type: ignore[return-value]
    raise_data_invalid(
        f"Unknown requirement token: {value!r}",
        path=path,
        details={"requires": value},
    )
    raise AssertionError("unreachable")


def parse_requires_list(raw: object, *, path: str | None = None) -> tuple[Requirement, ...]:
    if not raw:
        return ()
    if not isinstance(raw, (list, tuple, set, frozenset)):
        raise_data_invalid(
            f"requires must be an array, got {type(raw).__name__}",
            path=path,
        )
        raise AssertionError("unreachable")
    seen: list[Requirement] = []
    for item in raw:
        token = parse_requirement(item, path=path)
        if token not in seen:
            seen.append(token)
    return tuple(seen)


def tokens(node: dict[str, Any] | object | None) -> frozenset[Requirement]:
    if node is None:
        return frozenset()
    if isinstance(node, dict):
        raw = node.get("requires") or ()
    else:
        raw = getattr(node, "requires", ()) or ()
    return frozenset(parse_requires_list(raw))


def merge(*groups: Iterable[str]) -> frozenset[Requirement]:
    out: set[Requirement] = set()
    for group in groups:
        for item in group:
            out.add(parse_requirement(item))
    return frozenset(out)
