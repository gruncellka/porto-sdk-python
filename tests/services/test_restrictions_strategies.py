"""Independent legal / routing / impact strategy tests."""

from __future__ import annotations

from datetime import date

from porto_sdk.services.restrictions import impact as impact_mod
from porto_sdk.services.restrictions import legal as legal_mod
from porto_sdk.services.restrictions import routing as routing_mod
from porto_sdk.services.restrictions.types import LegalRestriction, RoutingRestriction


def _legal_region(*, partial: bool = False, jurisdictions: dict | None = None) -> dict:
    instruments = jurisdictions or {
        "EU": [{"reference": "https://example.test/eu", "effective_from": "2020-01-01"}],
        "UA": [{"reference": "https://example.test/ua", "effective_from": "2014-04-15"}],
    }
    row: dict = {
        "jurisdictions": instruments,
        "reason": "Regional legal restrictions apply.",
        "description": (
            "Applicable jurisdictional measures cover part of this region."
            if partial
            else "Applicable jurisdictional measures cover this region."
        ),
    }
    if partial:
        row["partial"] = True
    return row


def test_legal_filters_by_jurisdiction():
    catalog = {
        "UA": {
            "regions": {
                "UA-14": _legal_region(partial=True),
            }
        }
    }
    eu = legal_mod.resolve(
        catalog, "UA", "UA-14", jurisdictions={"EU"}, today=date(2026, 1, 1)
    )
    ua = legal_mod.resolve(
        catalog, "UA", "UA-14", jurisdictions={"UA"}, today=date(2026, 1, 1)
    )
    assert len(eu) == 1
    assert eu[0].impact == "warn"
    assert eu[0].partial is True
    assert eu[0].jurisdictions[0].jurisdiction == "EU"
    assert eu[0].jurisdictions[0].reference == "https://example.test/eu"
    assert ua[0].jurisdictions[0].jurisdiction == "UA"
    assert ua[0].jurisdictions[0].reference == "https://example.test/ua"


def test_legal_full_region_blocks():
    catalog = {"UA": {"regions": {"UA-43": _legal_region()}}}
    found = legal_mod.resolve(
        catalog, "UA", "UA-43", jurisdictions={"EU"}, today=date(2026, 1, 1)
    )
    assert found == [
        LegalRestriction(
            impact="block",
            country_code="UA",
            region_code="UA-43",
            partial=False,
            jurisdictions=found[0].jurisdictions,
            reason="Regional legal restrictions apply.",
            description="Applicable jurisdictional measures cover this region.",
        )
    ]


def test_legal_country_only_expands_regions():
    catalog = {
        "UA": {
            "regions": {
                "UA-43": _legal_region(),
                "UA-14": _legal_region(partial=True),
            }
        }
    }
    found = legal_mod.resolve(catalog, "UA", None, jurisdictions={"EU"}, today=date(2026, 1, 1))
    assert {item.region_code for item in found} == {"UA-43", "UA-14"}


def test_routing_is_destination_only():
    catalog = {
        "CY": {
            "authority": "CY",
            "reference": "https://example.test/cy",
            "reason": "forward",
            "description": "test",
            "regions": {"CY-01": {"partial": True}, "CY-06": {}},
        }
    }
    one = routing_mod.resolve(catalog, "CY", "CY-01")
    assert one == [
        RoutingRestriction(
            country_code="CY",
            region_code="CY-01",
            partial=True,
            authority="CY",
            reference="https://example.test/cy",
            reason="forward",
            description="test",
        )
    ]
    all_regions = routing_mod.resolve(catalog, "CY", None)
    assert {item.region_code for item in all_regions} == {"CY-01", "CY-06"}


def test_impact_country_only_warns_even_with_block_items():
    legal = [
        LegalRestriction(impact="block", country_code="UA", region_code="UA-43"),
        LegalRestriction(impact="warn", country_code="UA", region_code="UA-14", partial=True),
    ]
    assert impact_mod.resolve(legal, [], region_precise=False) == "warn"
    assert impact_mod.resolve(legal, [], region_precise=True) == "block"
    assert impact_mod.resolve([], [], region_precise=True) is None
