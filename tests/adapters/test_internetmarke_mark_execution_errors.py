"""Internetmarke mark-execution error classification (Portokasse wallet, RFC7807 titles)."""

import pytest

from porto_sdk.adapters.deutschepost.internetmarke.utils import (
    extract_internetmarke_vendor_error_code,
    is_retryable_error,
    map_internetmarke_error_code,
    parse_wallet_balance_cents,
    require_internetmarke_product_code,
)
from porto_sdk.errors import PortoError, PortoErrorCode


def test_extract_vendor_code_from_wallet_balance_title() -> None:
    err = {
        "statusCode": "400",
        "title": "walletBalanceNotEnough",
        "description": "A00627DFEF",
        "instance": "PCF-A1032",
    }
    assert extract_internetmarke_vendor_error_code(err) == "walletBalanceNotEnough"


def test_map_wallet_balance_not_enough_to_insufficient_funds() -> None:
    code = map_internetmarke_error_code("walletBalanceNotEnough", 400)
    assert code == PortoErrorCode.PORTO_WALLET_INSUFFICIENT
    assert is_retryable_error(400, "walletBalanceNotEnough") is False


def test_insufficient_funds_token_maps_to_wallet_insufficient() -> None:
    assert (
        map_internetmarke_error_code("INSUFFICIENT_FUNDS", 400)
        == PortoErrorCode.PORTO_WALLET_INSUFFICIENT
    )


def test_missing_vendor_code_stays_generic_for_400() -> None:
    assert map_internetmarke_error_code(None, 400) == PortoErrorCode.PORTO_MARK_FAILED


def test_parse_wallet_balance_from_auth_response() -> None:
    assert parse_wallet_balance_cents({"walletBalance": 80, "access_token": "x"}) == 80


def test_parse_wallet_balance_from_mark_response() -> None:
    assert parse_wallet_balance_cents({"walletBallance": 80}) == 80
    assert parse_wallet_balance_cents({"walletBalance": "125"}) == 125


def test_invalid_product_code_fails_closed() -> None:
    with pytest.raises(PortoError) as exc:
        require_internetmarke_product_code(None)
    assert exc.value.code == PortoErrorCode.PORTO_MARK_FAILED
    with pytest.raises(PortoError) as zero:
        require_internetmarke_product_code(0)
    assert zero.value.code == PortoErrorCode.PORTO_MARK_FAILED
    with pytest.raises(PortoError) as token:
        require_internetmarke_product_code("not-a-code")
    assert token.value.code == PortoErrorCode.PORTO_MARK_FAILED
