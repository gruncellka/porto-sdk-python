"""Layouts entity loader — formats/layouts.json"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BaseEntityLoader


@dataclass
class LayoutRect:
    x: float
    y: float
    width: float
    height: float


@dataclass
class EnvelopeLayout:
    envelope_id: str
    jurisdiction: str
    standard: str | None = None
    orientation: str | None = None
    window_supported: bool = False
    window_area: LayoutRect | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class LayoutsLoader(BaseEntityLoader):
    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._layouts: dict[str, dict[str, EnvelopeLayout]] = {}

    def load(self, data: dict[str, Any]) -> None:
        self._layouts = {}
        jurisdictions = data.get("jurisdictions") or {}
        for jurisdiction, payload in jurisdictions.items():
            envelopes = (payload or {}).get("envelopes") or {}
            bucket: dict[str, EnvelopeLayout] = {}
            for envelope_id, envelope_data in envelopes.items():
                layout = (envelope_data or {}).get("layout") or {}
                bucket[envelope_id] = EnvelopeLayout(
                    envelope_id=envelope_id,
                    jurisdiction=jurisdiction,
                    standard=(envelope_data or {}).get("standard"),
                    orientation=(envelope_data or {}).get("orientation"),
                    window_supported=bool((layout.get("window") or {}).get("supported")),
                    window_area=self._rect((layout.get("window") or {}).get("area")),
                    raw=envelope_data or {},
                )
            self._layouts[jurisdiction] = bucket

    def get_data(self) -> dict[str, dict[str, EnvelopeLayout]]:
        return self._layouts

    def get_layout(self, jurisdiction: str, envelope_id: str) -> EnvelopeLayout | None:
        return (self._layouts.get(jurisdiction) or {}).get(envelope_id)

    @staticmethod
    def _rect(raw: Any) -> LayoutRect | None:
        if not isinstance(raw, dict):
            return None
        try:
            return LayoutRect(
                x=float(raw["x"]),
                y=float(raw["y"]),
                width=float(raw["width"]),
                height=float(raw["height"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
