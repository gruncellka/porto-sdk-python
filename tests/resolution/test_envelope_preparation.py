"""Envelope paper preparation (sheets/fold) on envelopeResolver public API."""

from porto_sdk import PortoClient, PortoConfig
from porto_sdk.config import ProviderRuntimeConfig
from porto_sdk.data.entities.envelopes import PortoEnvelope
from porto_sdk.services.envelope_resolver import format_envelope_sheets


def test_format_envelope_sheets_skips_incomplete_rows() -> None:
    envelope = PortoEnvelope(
        id="DL",
        label="DL",
        width=220,
        height=110,
        sheets=[
            {"sheet": "A4", "fold": "trifold", "description": "thirds"},
            {"sheet": "", "fold": "half"},
            {"sheet": "A5", "fold": ""},
        ],
    )
    rows = format_envelope_sheets(envelope)
    assert len(rows) == 1
    assert rows[0]["sheet"] == "A4"
    assert rows[0]["fold"] == "trifold"
    assert rows[0]["description"] == "thirds"


def test_envelope_resolver_list_includes_sheets() -> None:
    client = PortoClient(
        PortoConfig(
            providers={"deutschepost": ProviderRuntimeConfig()}, strict_data_validation=False
        )
    )
    rows = client.envelopes.list()
    dl = next(r for r in rows if r["id"] == "DL")
    c5 = next(r for r in rows if r["id"] == "C5")
    assert any(s["sheet"] == "A4" and s["fold"] == "trifold" for s in dl["sheets"])
    assert any(s["sheet"] == "A4" and s["fold"] == "half" for s in c5["sheets"])
