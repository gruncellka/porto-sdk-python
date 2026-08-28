"""Marks entity loader — providers/<id>/marks.json"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...execution import MarkType, parse_mark_type
from ...requires import Requirement, parse_requires_list
from .base import BaseEntityLoader


@dataclass
class MarkProfile:
    id: str
    mark_type: MarkType
    label: str
    width: float
    height: float
    mime_types: list[str] = field(default_factory=list)
    requires: tuple[Requirement, ...] = ()
    clearance: float | None = None


@dataclass(frozen=True)
class MarkRect:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class MarkAssetSize:
    width_px: int
    height_px: int
    width_mm: float
    height_mm: float


@dataclass
class MarkCalibration:
    """One ``marks.json`` ``calibrations[]`` row.

    ``mark_profile`` is the **wire mark-layout token** (e.g. Internetmarke
    ``FRANKING_ZONE`` / ``ADDRESS_ZONE``), not ``profiles[].id``. Porto profile
    ids select entries under ``by_mark_profile``.
    """

    wire: str
    mark_profile: str
    mime_type: str
    dpi: int
    by_mark_profile: dict[str, MarkAssetSize] = field(default_factory=dict)
    label_canvas: MarkAssetSize | None = None


def _parse_rect(raw: Any) -> MarkRect | None:
    if not isinstance(raw, dict):
        return None
    try:
        return MarkRect(
            x=float(raw["x"]),
            y=float(raw["y"]),
            width=float(raw["width"]),
            height=float(raw["height"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _parse_asset_size(raw: Any) -> MarkAssetSize | None:
    if not isinstance(raw, dict):
        return None
    try:
        return MarkAssetSize(
            width_px=int(raw["width_px"]),
            height_px=int(raw["height_px"]),
            width_mm=float(raw["width_mm"]),
            height_mm=float(raw["height_mm"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


class MarksLoader(BaseEntityLoader):
    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._profiles: dict[str, MarkProfile] = {}
        self._default_profile_id: str | None = None
        self._calibrations: list[MarkCalibration] = []
        self._placement: dict[str, MarkRect] = {}

    def load(self, data: dict[str, Any]) -> None:
        self._profiles = {}
        self._calibrations = []
        self._placement = {}
        self._default_profile_id = data.get("default_profile")
        for row in data.get("profiles") or []:
            size = row.get("size") or {}
            clearance_raw = row.get("clearance")
            try:
                clearance = float(clearance_raw) if clearance_raw is not None else None
            except (TypeError, ValueError):
                clearance = None
            profile = MarkProfile(
                id=str(row["id"]),
                mark_type=parse_mark_type(row.get("type") or row.get("mark_type")),
                label=str(row.get("label", row["id"])),
                width=float(size.get("width", 0)),
                height=float(size.get("height", 0)),
                mime_types=list(row.get("mime_type") or []),
                requires=parse_requires_list(row.get("requires"), path="marks.requires"),
                clearance=clearance,
            )
            self._profiles[profile.id] = profile

        envelopes_map = (data.get("placement") or {}).get("envelopes") or {}
        if isinstance(envelopes_map, dict):
            for envelope_id, raw in envelopes_map.items():
                parsed = _parse_rect(raw)
                if parsed is not None:
                    self._placement[str(envelope_id)] = parsed

        for row in data.get("calibrations") or []:
            if not isinstance(row, dict):
                continue
            by_profile: dict[str, MarkAssetSize] = {}
            raw_by = row.get("by_mark_profile")
            if isinstance(raw_by, dict):
                for profile_id, dims in raw_by.items():
                    asset = _parse_asset_size(dims)
                    if asset is not None:
                        by_profile[str(profile_id)] = asset
            self._calibrations.append(
                MarkCalibration(
                    wire=str(row.get("wire") or ""),
                    mark_profile=str(row.get("mark_profile") or ""),
                    mime_type=str(row.get("mime_type") or "image/png"),
                    dpi=int(row.get("dpi") or 0),
                    by_mark_profile=by_profile,
                    label_canvas=_parse_asset_size(row.get("label_canvas")),
                )
            )

    def get_data(self) -> dict[str, MarkProfile]:
        return self._profiles

    def get_profile(self, profile_id: str) -> MarkProfile | None:
        return self._profiles.get(profile_id)

    def get_default_profile(self) -> MarkProfile | None:
        if self._default_profile_id:
            return self._profiles.get(self._default_profile_id)
        return next(iter(self._profiles.values()), None)

    def get_default_profile_id(self) -> str | None:
        return self._default_profile_id

    def get_placement(self, envelope_id: str) -> MarkRect | None:
        return self._placement.get(envelope_id)

    def get_calibrations(self) -> list[MarkCalibration]:
        return list(self._calibrations)

    def get_calibration(
        self,
        *,
        wire: str,
        mark_profile: str,
        mime_type: str = "image/png",
        dpi: int = 300,
    ) -> MarkCalibration | None:
        """Lookup by wire + ``calibrations[].mark_profile`` (layout token)."""
        for row in self._calibrations:
            if (
                row.wire == wire
                and row.mark_profile == mark_profile
                and row.mime_type == mime_type
                and row.dpi == dpi
            ):
                return row
        return None

    def get_calibration_asset_size(
        self,
        *,
        wire: str,
        mark_profile: str,
        mark_profile_id: str | None = None,
        mime_type: str = "image/png",
        dpi: int = 300,
    ) -> MarkAssetSize | None:
        """Resolve measured size for a mark layout + optional Porto profile id."""
        row = self.get_calibration(
            wire=wire, mark_profile=mark_profile, mime_type=mime_type, dpi=dpi
        )
        if row is None:
            return None
        if mark_profile_id and mark_profile_id in row.by_mark_profile:
            return row.by_mark_profile[mark_profile_id]
        return row.label_canvas
