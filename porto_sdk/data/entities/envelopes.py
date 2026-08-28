"""Envelopes entity loader — formats/envelopes.json"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BaseEntityLoader


@dataclass
class PortoEnvelope:
    id: str
    label: str
    width: int
    height: int
    standards: list[str] = field(default_factory=list)
    sheets: list[dict[str, Any]] = field(default_factory=list)
    notes: str | None = None


class EnvelopesLoader(BaseEntityLoader):
    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._envelopes: dict[str, PortoEnvelope] = {}

    def load(self, data: dict[str, Any]) -> None:
        self._envelopes = {}
        for row in data.get("envelopes", []):
            raw_standards = row.get("standards")
            if isinstance(raw_standards, list):
                standards = [str(item) for item in raw_standards]
            elif row.get("standard"):
                standards = [str(row["standard"])]
            else:
                standards = []
            envelope = PortoEnvelope(
                id=str(row["id"]),
                label=str(row.get("label", row["id"])),
                width=int(row["width"]),
                height=int(row["height"]),
                standards=standards,
                sheets=list(row.get("sheets") or []),
                notes=row.get("notes"),
            )
            self._envelopes[envelope.id] = envelope

    def get_data(self) -> dict[str, PortoEnvelope]:
        return self._envelopes

    def get_envelope(self, envelope_id: str) -> PortoEnvelope | None:
        return self._envelopes.get(envelope_id)

    def list_envelopes(self) -> list[PortoEnvelope]:
        return list(self._envelopes.values())

    def all_ids(self) -> set[str]:
        return set(self._envelopes.keys())
