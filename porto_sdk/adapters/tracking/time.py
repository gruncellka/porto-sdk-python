"""Carrier-reported tracking time syntax, without timezone inference."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, NamedTuple

OccurredKind = Literal["offset", "local"]

_DATETIME = re.compile(
    r"^(?P<base>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<fraction>\d+))?"
    r"(?P<offset>Z|[+-]\d{2}:\d{2})?$"
)


class OccurredTime(NamedTuple):
    value: str
    kind: OccurredKind


def normalize_occurred_at(value: object | None) -> OccurredTime | None:
    """Preserve an offset or zoneless carrier datetime; reject inferred clocks."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = _DATETIME.fullmatch(text)
    if match is None:
        return None

    base = match.group("base")
    fraction = match.group("fraction")
    offset = match.group("offset") or ""
    normalized_fraction = f".{fraction[:3].ljust(3, '0')}" if fraction else ""
    normalized = f"{base}{normalized_fraction}{offset}"
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return OccurredTime(normalized, "offset" if offset else "local")
