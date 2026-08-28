"""Licko-style address fixtures from porto-features.

Default country order: DE, UA, FR, CH, US.
``origin_DE`` is the DE sender twin of ``valid_DE``.
"""

from __future__ import annotations

import json
from typing import Any

from porto_sdk.types import Address

LICKO_COUNTRIES = ("DE", "UA", "FR", "CH", "US")
_ALPHA3 = {"DE": "DEU", "UA": "UKR", "FR": "FRA", "CH": "CHE", "US": "USA"}


def load_address_fixture(fixture_id: str) -> dict[str, Any]:
    from tests.support.porto_features_path import get_fixtures_dir

    path = get_fixtures_dir() / "addresses" / f"{fixture_id}.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def valid_address_id(country: str) -> str:
    code = country.strip().upper()
    if code not in LICKO_COUNTRIES:
        raise ValueError(f"No licko address fixture for {country!r}; use {LICKO_COUNTRIES}")
    return f"valid_{code}"


def address_json(fixture_id: str) -> dict[str, Any]:
    return {key: value for key, value in load_address_fixture(fixture_id).items() if key != "id"}


def address_from_fixture(fixture_id: str) -> Address:
    raw = load_address_fixture(fixture_id)
    return Address(
        name=str(raw["name"]),
        street=str(raw.get("street") or "") or None,
        house_number=str(raw["house_number"]) if raw.get("house_number") is not None else None,
        postal_code=str(raw["postal_code"]),
        locality=str(raw["locality"]),
        country_code=str(raw["country_code"]),
        region_code=raw.get("region_code"),
    )


def licko_sender() -> Address:
    return address_from_fixture("origin_DE")


def licko_recipient(country: str = "DE") -> Address:
    return address_from_fixture(valid_address_id(country))


def internetmarke_cart_address(fixture_id: str) -> dict[str, str]:
    raw = load_address_fixture(fixture_id)
    country = str(raw["country_code"])
    street = str(raw.get("street") or "")
    house = str(raw.get("house_number") or "")
    line = f"{street} {house}".strip()
    return {
        "name": str(raw["name"]),
        "addressLine1": line,
        "postalCode": str(raw["postal_code"]),
        "city": str(raw["locality"]),
        "country": _ALPHA3[country],
    }
