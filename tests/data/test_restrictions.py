from datetime import date
from pathlib import Path

import pytest

from porto_sdk.data.entities.restrictions import RestrictionsLoader
from porto_sdk.errors import DataError, PortoErrorCode


def _region(*, partial: bool = False, jurisdictions: dict | None = None) -> dict:
    payload: dict = {
        "jurisdictions": jurisdictions
        or {
            "EU": [
                {
                    "reference": "https://example.test/eu",
                    "effective_from": "2020-01-01",
                    "effective_to": None,
                }
            ]
        },
        "reason": "Regional legal restrictions apply.",
        "description": (
            "Applicable jurisdictional measures cover part of this region."
            if partial
            else "Applicable jurisdictional measures cover this region."
        ),
    }
    if partial:
        payload["partial"] = True
    return payload


def _loader(*, legal: dict | None = None) -> RestrictionsLoader:
    loader = RestrictionsLoader(Path("."), {})
    payload: dict = {"file_type": "restrictions"}
    if legal is not None:
        payload["legal"] = legal
    loader.load(payload)
    return loader


def test_load_fails_closed_without_jurisdictions():
    loader = RestrictionsLoader(Path("."), {})
    with pytest.raises(DataError) as exc:
        loader.load(
            {
                "legal": {
                    "UA": {
                        "regions": {
                            "UA-14": {},
                        }
                    }
                }
            }
        )
    assert exc.value.code == PortoErrorCode.PORTO_DATA_INVALID


def test_load_fails_closed_when_routing_has_jurisdictions():
    loader = RestrictionsLoader(Path("."), {})
    with pytest.raises(DataError) as exc:
        loader.load(
            {
                "routing": {
                    "CY": {
                        "authority": "CY",
                        "reference": "https://example.test/cy",
                        "reason": "x",
                        "description": "x",
                        "jurisdictions": {
                            "EU": [{"reference": None, "effective_from": "2020-01-01"}]
                        },
                    }
                }
            }
        )
    assert exc.value.code == PortoErrorCode.PORTO_DATA_INVALID


def test_load_fails_closed_on_frameworks_key():
    loader = RestrictionsLoader(Path("."), {})
    with pytest.raises(DataError) as exc:
        loader.load(
            {
                "legal": {
                    "UA": {
                        "regions": {
                            "UA-14": {
                                "frameworks": {
                                    "EU": [{"reference": None, "effective_from": "2020-01-01"}]
                                },
                            }
                        }
                    }
                }
            }
        )
    assert exc.value.code == PortoErrorCode.PORTO_DATA_INVALID


def test_load_fails_closed_on_unknown_jurisdiction():
    loader = RestrictionsLoader(Path("."), {})
    with pytest.raises(DataError) as exc:
        loader.load(
            {
                "legal": {
                    "DE": {
                        "jurisdictions": {
                            "UN": [{"reference": None, "effective_from": "2020-01-01"}]
                        },
                        "reason": "Regional legal restrictions apply.",
                        "description": "Applicable jurisdictional measures cover this region.",
                    }
                }
            }
        )
    assert exc.value.code == PortoErrorCode.PORTO_DATA_INVALID


def test_country_check_returns_regional_legal_facts():
    loader = _loader(
        legal={
            "UA": {
                "regions": {
                    "UA-14": _region(partial=True),
                    "UA-43": _region(),
                }
            }
        }
    )
    selected = loader.classify_restrictions("UA", jurisdictions={"EU"})
    assert set(selected["legal"]["UA"]["regions"]) == {"UA-14", "UA-43"}
    assert selected["routing"] == {}


def test_region_code_selects_matching_legal_fact():
    loader = _loader(
        legal={
            "UA": {
                "regions": {
                    "UA-14": _region(partial=True),
                    "UA-43": _region(),
                }
            }
        }
    )
    selected = loader.classify_restrictions("UA", "UA-14", jurisdictions={"EU"})
    assert set(selected["legal"]["UA"]["regions"]) == {"UA-14"}


def test_provider_filter_keeps_only_matching_jurisdiction():
    loader = _loader(
        legal={
            "UA": {
                "regions": {
                    "UA-14": _region(
                        partial=True,
                        jurisdictions={
                            "EU": [
                                {
                                    "reference": "https://example.test/eu",
                                    "effective_from": "2020-01-01",
                                    "effective_to": None,
                                }
                            ],
                            "UA": [
                                {
                                    "reference": "https://example.test/ua",
                                    "effective_from": "2014-04-15",
                                    "effective_to": None,
                                }
                            ],
                        },
                    )
                }
            }
        }
    )
    eu_rows = loader.classify_restrictions("UA", "UA-14", jurisdictions={"EU"})["legal"]
    ua_rows = loader.classify_restrictions("UA", "UA-14", jurisdictions={"UA"})["legal"]
    assert set(eu_rows["UA"]["regions"]["UA-14"]["jurisdictions"]) == {"EU"}
    assert set(ua_rows["UA"]["regions"]["UA-14"]["jurisdictions"]) == {"UA"}


def test_future_instrument_is_ignored():
    loader = _loader(
        legal={
            "DE": {
                "jurisdictions": {
                    "EU": [
                        {
                            "reference": None,
                            "effective_from": "2999-01-01",
                            "effective_to": None,
                        }
                    ]
                },
                "reason": "Regional legal restrictions apply.",
                "description": "Applicable jurisdictional measures cover this region.",
            }
        }
    )
    selected = loader.classify_restrictions("DE", jurisdictions={"EU"}, as_of=date(2026, 1, 1))
    assert selected["legal"] == {}


def test_expired_instrument_is_ignored():
    loader = _loader(
        legal={
            "DE": {
                "jurisdictions": {
                    "EU": [
                        {
                            "reference": None,
                            "effective_from": "2000-01-01",
                            "effective_to": "2001-01-01",
                        }
                    ]
                },
                "reason": "Regional legal restrictions apply.",
                "description": "Applicable jurisdictional measures cover this region.",
            }
        }
    )
    selected = loader.classify_restrictions("DE", jurisdictions={"EU"}, as_of=date(2026, 1, 1))
    assert selected["legal"] == {}


def test_catalog_ua14_returns_legal_fact_for_default_client(client):
    found = client.restrictions.check("UA", "UA-14")
    assert found.impact == "warn"
    assert len(found.legal) == 1
    item = found.legal[0]
    assert item.region_code == "UA-14"
    assert item.partial is True
    assert item.jurisdictions[0].jurisdiction == "EU"
    assert item.jurisdictions[0].reference.startswith("https://eur-lex.europa.eu")
    assert found.routing == ()


def test_load_fails_closed_on_operational_collection():
    loader = RestrictionsLoader(Path("."), {})
    with pytest.raises(DataError) as exc:
        loader.load(
            {
                "operational": {
                    "HT": {
                        "authority": "x",
                        "reference": "x",
                        "reason": "x",
                        "description": "x",
                        "effective_from": "2020-01-01",
                    }
                }
            }
        )
    assert exc.value.code == PortoErrorCode.PORTO_DATA_INVALID
