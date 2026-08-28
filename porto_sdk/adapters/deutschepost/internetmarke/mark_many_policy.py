"""Internetmarke mark(many) entry checks before shopping-cart checkout.

Empty list or missing Porto identity → PORTO_MARK_INVALID.
Mixed Portos are allowed; provider rejection maps to PORTO_MARK_FAILED upstream.
"""

from __future__ import annotations

from collections.abc import Sequence

from ....errors import PortoError, PortoErrorCode
from ....execution import MarkExecution


def require_mark_many_prepared(prepared: Sequence[MarkExecution]) -> None:
    """Fail only when the list is empty or an item lacks Porto identity."""
    if not prepared:
        raise PortoError(
            "mark(many) requires at least one request",
            PortoErrorCode.PORTO_MARK_INVALID,
            status_code=400,
            retryable=False,
            provider="deutschepost",
            wire="internetmarke",
        )
    for item in prepared:
        if item.porto is None:
            raise PortoError(
                "Prepared mark is missing Porto identity",
                PortoErrorCode.PORTO_MARK_INVALID,
                status_code=400,
                retryable=False,
                provider="deutschepost",
                wire="internetmarke",
            )
