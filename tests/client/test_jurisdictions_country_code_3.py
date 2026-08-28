"""Unit tests for jurisdictions.country_code_3 (alpha-2 → alpha-3)."""

from porto_sdk import PortoClient
from porto_sdk.errors import PortoError, PortoErrorCode


def test_country_code_3_known_codes():
    client = PortoClient()
    assert client.jurisdictions.country_code_3("IE") == "IRL"
    assert client.jurisdictions.country_code_3("BG") == "BGR"
    assert client.jurisdictions.country_code_3("DE") == "DEU"
    assert client.jurisdictions.country_code_3("US") == "USA"
    assert client.jurisdictions.country_code_3("jp") == "JPN"


def test_every_country_key_has_country_code_3():
    client = PortoClient()
    codes = client.jurisdictions.country_codes()
    assert len(codes) >= 100
    for alpha2 in codes:
        alpha3 = client.jurisdictions.country_code_3(alpha2)
        assert len(alpha3) == 3
        assert alpha3.isalpha()
        assert alpha3.isupper()


def test_country_code_3_unknown_raises():
    client = PortoClient()
    try:
        client.jurisdictions.country_code_3("ZZ")
        raise AssertionError("expected PortoError")
    except PortoError as err:
        assert err.code == PortoErrorCode.PORTO_DESTINATION_INVALID
