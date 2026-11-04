"""Cross-SDK tracking time contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from porto_sdk.adapters.deutschepost.tracking.shipment import snapshot
from porto_sdk.adapters.tracking.adapter import assemble_tracking, map_event
from porto_sdk.adapters.tracking.time import normalize_occurred_at
from porto_sdk.types import PortoStatus

CONTRACT = json.loads(Path(__file__).with_name("time-cases.json").read_text(encoding="utf-8"))
CASES = CONTRACT["normalization"]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_normalize_occurred_at(case: dict[str, str | None]) -> None:
    result = normalize_occurred_at(case["input"])
    if case["value"] is None:
        assert result is None
    else:
        assert result is not None
        assert result.value == case["value"]
        assert result.kind == case["kind"]


def _event(
    code: str,
    occurred_at: str | None,
    sequence: int,
    *,
    received_at: str = "2026-01-01T13:00:00+00:00",
):
    return map_event(
        provider_id="deutschepost",
        tracking_number="TRACK",
        native_code=code,
        native_label=None,
        occurred_at=occurred_at,
        received_at=received_at,
        native_sequence=sequence,
    )


def test_assembly_separates_last_update_from_status_change() -> None:
    case = CONTRACT["assembly"]
    history = [_event(row["code"], row["occurredAt"], row["sequence"]) for row in case["events"]]
    assembled = assemble_tracking(history)
    assert assembled.status.value == case["status"]
    assert assembled.last_update == case["lastUpdate"]
    assert assembled.status_changed_at == case["statusChangedAt"]

    delivered = assemble_tracking([*history, _event("delivered", "2026-01-01T12:00:00+00:00", 3)])
    assert delivered.status is PortoStatus.DELIVERED
    assert delivered.last_update == "2026-01-01T12:00:00+00:00"
    assert delivered.status_changed_at == "2026-01-01T12:00:00+00:00"


@pytest.mark.parametrize(
    "case",
    CONTRACT["identity"],
    ids=[case["name"] for case in CONTRACT["identity"]],
)
def test_event_identity_contract(case: dict) -> None:
    event = map_event(
        provider_id=case["provider"],
        tracking_number=case["tracking"],
        native_code=case["code"],
        native_label=None,
        occurred_at=case["occurredAt"],
        received_at="2026-01-01T13:00:00+00:00",
        native_sequence=case["sequence"],
        native_index=case["index"],
    )
    assert event.event_id == case["eventId"]


def test_event_identity_prefers_native_sequence_over_poll_or_time() -> None:
    first = _event("transit", None, 7, received_at="2026-01-01T13:00:00+00:00")
    repeated = _event("transit", None, 7, received_at="2026-01-02T13:00:00+00:00")
    same_time_other_event = _event("transit", None, 8)
    assert first.event_id == repeated.event_id
    assert same_time_other_event.event_id != first.event_id
    assert first.occurred_at is None
    assert first.occurred_kind is None


def test_event_identity_has_explicit_index_fallback() -> None:
    args = {
        "provider_id": "deutschepost",
        "tracking_number": "TRACK",
        "native_code": "transit",
        "native_label": None,
        "occurred_at": None,
        "received_at": "2026-01-01T13:00:00+00:00",
    }
    assert map_event(**args, native_index=0).event_id == map_event(**args, native_index=0).event_id
    assert map_event(**args, native_index=0).event_id != map_event(**args, native_index=1).event_id


def test_ukrposhta_real_event_id_keeps_local_time_without_changing_acl() -> None:
    event = map_event(
        provider_id="ukrposhta",
        tracking_number="0500100031143",
        native_code="41000",
        native_label="Delivery",
        occurred_at="2023-05-20T17:38:00",
        received_at="2023-05-20T18:00:00+00:00",
        native_sequence=16,
    )
    assert event.provider_code == "41000"
    assert event.occurred_at == "2023-05-20T17:38:00"
    assert event.occurred_kind == "local"
    assert event.status is None


def test_laposte_event_date_keeps_explicit_offset() -> None:
    event = map_event(
        provider_id="laposte",
        tracking_number="TRACK",
        native_code="PC2",
        native_label="In transit",
        occurred_at="2017-12-02T09:11:00+02:00",
        received_at="2017-12-02T10:00:00+00:00",
        native_index=0,
    )
    assert event.occurred_at == "2017-12-02T09:11:00+02:00"
    assert event.occurred_kind == "offset"
    assert event.status is PortoStatus.TRANSIT


def test_dp_uses_timestamp_and_never_processing_date_or_poll_time() -> None:
    result = snapshot(
        tracking_number="TRACK",
        payload={
            "events": [
                {
                    "historicalState": "transit",
                    "timestamp": "2026-01-01T10:00:00.123456789+00:00",
                    "processingDate": "2026-01-01",
                    "sequence": 1,
                },
                {
                    "historicalState": "transit",
                    "processingDate": "2026-01-02",
                    "sequence": 2,
                },
            ]
        },
    )
    assert result.history[0].occurred_at == "2026-01-01T10:00:00.123+00:00"
    assert result.history[0].occurred_kind == "offset"
    assert result.history[1].occurred_at is None
    assert result.last_update is None
    assert result.status_changed_at == "2026-01-01T10:00:00.123+00:00"
    assert result.poll_received_at not in {
        result.history[0].occurred_at,
        result.history[1].occurred_at,
        result.last_update,
        result.status_changed_at,
    }
