"""Licko-style porto-features addresses: DE → UA → FR → CH → US."""

from tests.support.addresses import LICKO_COUNTRIES, licko_recipient, licko_sender


def test_licko_country_priority_order() -> None:
    assert LICKO_COUNTRIES == ("DE", "UA", "FR", "CH", "US")


def test_licko_sender_is_german_origin() -> None:
    sender = licko_sender()
    assert sender.country_code == "DE"
    assert sender.name == "Porto SDK"


def test_licko_recipients_load_in_priority_order() -> None:
    for country in LICKO_COUNTRIES:
        address = licko_recipient(country)
        assert address.country_code == country
        assert address.locality
        assert address.postal_code
