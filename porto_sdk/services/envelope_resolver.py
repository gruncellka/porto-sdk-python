from __future__ import annotations

import builtins
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..data.entities.envelopes import PortoEnvelope
from ..data.loader import PortoDataLoader
from ..envelopes import EnvelopeMatchService, JsonFormatCatalog
from ..envelopes.types import (
    Envelope,
    EnvelopeGeometry,
    EnvelopeLayout,
    EnvelopeMark,
    EnvelopeMarkFact,
    EnvelopeRect,
    EnvelopeSheet,
    EnvelopeSize,
    Match,
)
from ..errors import PortoError, PortoErrorCode
from ..types import Dimensions
from .execution_binding import ExecutionBinding
from .validation import LetterValidationService


def format_envelope_sheets(envelope: PortoEnvelope) -> builtins.list[EnvelopeSheet]:
    """Paper preparation hints from porto-data formats/envelopes.json sheets[]."""
    rows: builtins.list[EnvelopeSheet] = []
    for raw in envelope.sheets or []:
        sheet = str(raw.get("sheet", "")).strip()
        fold = str(raw.get("fold", "")).strip()
        if not sheet or not fold:
            continue
        description = raw.get("description")
        rows.append(
            EnvelopeSheet(
                sheet=sheet,
                fold=fold,
                description=str(description) if description else None,
            )
        )
    return rows


@dataclass(frozen=True)
class EnvelopeIdentity:
    dimensions: Dimensions
    format: str | None
    resolution_weight: int


@runtime_checkable
class Envelopes(Protocol):
    """Public catalog façade for ``client.envelopes``."""

    def list(self) -> builtins.list[Envelope]: ...

    def geometry(self, envelope_id: str, jurisdiction: str | None = None) -> EnvelopeGeometry: ...

    def layout(
        self,
        envelope_id: str,
        jurisdiction: str | None = None,
        product_id: str | None = None,
        *,
        zone_id: str | None = None,
        service_ids: builtins.list[str] | None = None,
    ) -> EnvelopeLayout: ...

    def get_mark(
        self,
        product_id: str | None = None,
        *,
        envelope_id: str | None = None,
        zone_id: str | None = None,
        service_ids: builtins.list[str] | None = None,
    ) -> EnvelopeMark: ...

    async def identify(
        self,
        *,
        envelope_format: str | None = None,
        dimensions: dict[str, Any] | None = None,
        weight: int,
    ) -> EnvelopeIdentity: ...

    def validate_for_product(self, envelope_id: str, product_id: str) -> Match: ...

    def resolve(
        self, candidate: dict[str, object], product_id: str, mode: str | None = None
    ) -> Match: ...


class EnvelopeResolverService:
    def __init__(
        self,
        validation: LetterValidationService,
        data_loader: PortoDataLoader,
    ):
        self.validation = validation
        self.data_loader = data_loader
        self._binding = ExecutionBinding(data_loader)
        self._match_service = EnvelopeMatchService(JsonFormatCatalog(data_loader._envelopes_loader))

    def normalize_envelope_format(self, value: str) -> str:
        normalized = value.strip().upper().replace(" ", "").replace("_", "").replace("-", "")
        if normalized in self._get_envelope_format_map():
            return normalized
        supported = ", ".join(self.list_supported_formats())
        raise ValueError(f"Unknown envelope format '{value}'. Supported formats: {supported}.")

    def list_supported_formats(self) -> builtins.list[str]:
        return list(self._get_envelope_format_map().keys())

    def validate_ident_input(self, args: Any) -> None:
        issues: builtins.list[str] = []

        missing_top: builtins.list[str] = []
        if getattr(args, "country", None) in (None, ""):
            missing_top.append("--country")
        if getattr(args, "weight", None) in (None, ""):
            missing_top.append("--weight")
        if missing_top:
            issues.append(f"missing {', '.join(missing_top)}")

        has_format = bool(getattr(args, "format", None))
        has_length = getattr(args, "length", None) is not None
        has_width = getattr(args, "width", None) is not None
        has_height = getattr(args, "height", None) is not None
        has_any_dimensions = has_length or has_width or has_height

        if not has_format and not has_any_dimensions:
            issues.append("provide either --format or all of --length --width --height")
        elif has_format and has_any_dimensions:
            issues.append("use either --format OR --length --width --height, not both")
        elif not has_format:
            missing_dims: builtins.list[str] = []
            if not has_length:
                missing_dims.append("--length")
            if not has_width:
                missing_dims.append("--width")
            if not has_height:
                missing_dims.append("--height")
            if missing_dims:
                issues.append(f"missing {', '.join(missing_dims)} for dimension mode")

        if issues:
            raise ValueError(f"Invalid input for 'ident': {'; '.join(issues)}.")

    def parse_dimensions(
        self,
        *,
        envelope_format: str | None,
        dimensions: dict[str, Any] | None,
    ) -> dict[str, float]:
        dims = dimensions or {}
        has_format = bool(envelope_format)
        has_any_dimensions = (
            dims.get("length") is not None
            or dims.get("width") is not None
            or dims.get("height") is not None
        )

        if has_format and has_any_dimensions:
            raise ValueError("Use either --format OR --length --width --height, not both.")

        if has_format:
            normalized = self.normalize_envelope_format(str(envelope_format))
            return {k: float(v) for k, v in self._get_envelope_format_map()[normalized].items()}

        if dims.get("length") is None or dims.get("width") is None or dims.get("height") is None:
            raise ValueError(
                "Provide --format (e.g., C5) or all of --length --width --height in mm."
            )

        result: dict[str, float] = {
            "length": float(dims["length"]),
            "width": float(dims["width"]),
            "height": float(dims["height"]),
        }
        if dims.get("thickness") is not None:
            result["thickness"] = float(dims["thickness"])
        return result

    def detect_envelope_format(self, dimensions: dict[str, float]) -> str | None:
        length = float(dimensions["length"])
        width = float(dimensions["width"])
        height = float(dimensions["height"])
        for envelope_format, spec in self._get_envelope_format_map().items():
            same_orientation = (
                length == float(spec["length"])
                and width == float(spec["width"])
                and height == float(spec["height"])
            )
            swapped_orientation = (
                length == float(spec["width"])
                and width == float(spec["length"])
                and height == float(spec["height"])
            )
            if same_orientation or swapped_orientation:
                return envelope_format
        return None

    async def identify(
        self,
        *,
        envelope_format: str | None = None,
        dimensions: dict[str, Any] | None = None,
        weight: int,
    ) -> EnvelopeIdentity:
        from .resolution import WeightTierResolver

        parsed_dimensions = self.parse_dimensions(
            envelope_format=envelope_format,
            dimensions=dimensions,
        )
        model_dimensions = Dimensions(**parsed_dimensions)
        dimension_validation = await self.validation.validate_dimensions(model_dimensions)
        if not dimension_validation.is_valid:
            raise ValueError(f"Invalid dimensions: {'; '.join(dimension_validation.errors)}")

        weight_tier_id = WeightTierResolver(self.data_loader).resolve(weight)
        if not weight_tier_id:
            raise PortoError(
                f"Weight {weight}g exceeds maximum",
                PortoErrorCode.PORTO_TOO_HEAVY,
                status_code=400,
                details={"weight": weight},
            )

        detected_format = self.detect_envelope_format(parsed_dimensions)
        return EnvelopeIdentity(
            dimensions=model_dimensions,
            format=detected_format,
            resolution_weight=weight,
        )

    def list_policy_format_ids(self) -> builtins.list[str]:
        return [e.id for e in self.data_loader.list_envelopes()]

    def list(self) -> builtins.list[Envelope]:
        return [
            Envelope(
                id=e.id,
                name=e.label,
                width=e.width,
                height=e.height,
                sheets=tuple(format_envelope_sheets(e)),
            )
            for e in self.data_loader.list_envelopes()
        ]

    def geometry(self, envelope_id: str, jurisdiction: str | None = None) -> EnvelopeGeometry:
        envelope = self._require_envelope(envelope_id)
        return EnvelopeGeometry(
            id=envelope.id,
            name=envelope.label,
            width=envelope.width,
            height=envelope.height,
            sheets=tuple(format_envelope_sheets(envelope)),
            window=self._window_rect(envelope_id, jurisdiction),
            notes=envelope.notes or None,
        )

    def layout(
        self,
        envelope_id: str,
        jurisdiction: str | None = None,
        product_id: str | None = None,
        *,
        zone_id: str | None = None,
        service_ids: builtins.list[str] | None = None,
    ) -> EnvelopeLayout:
        envelope = self._require_envelope(envelope_id)
        return EnvelopeLayout(
            envelope_id=envelope_id,
            width=envelope.width,
            height=envelope.height,
            window=self._window_rect(envelope_id, jurisdiction),
            mark=self._layout_mark(
                envelope_id=envelope_id,
                product_id=product_id,
                zone_id=zone_id,
                service_ids=service_ids,
            ),
        )

    def get_mark(
        self,
        product_id: str | None = None,
        *,
        envelope_id: str | None = None,
        zone_id: str | None = None,
        service_ids: builtins.list[str] | None = None,
    ) -> EnvelopeMark:
        mark = self._layout_mark(
            envelope_id=envelope_id,
            product_id=product_id,
            zone_id=zone_id,
            service_ids=service_ids,
        )
        if mark is None:
            raise PortoError(
                "Mark profile not found",
                PortoErrorCode.PORTO_DATA_NOT_FOUND,
                status_code=404,
            )
        return EnvelopeMark(
            provider_id=self.data_loader.provider_id,
            profile_id=mark.profile_id,
            type=mark.type,
            size=mark.size,
            product_id=product_id,
            zone_id=zone_id,
            clearance=mark.clearance,
            placement=mark.placement,
        )

    def match(self, envelope_id: str, product_id: str) -> Match:
        product = self.data_loader.get_product(product_id)
        if product is None:
            raise PortoError(
                f"Product not found: {product_id}",
                PortoErrorCode.PORTO_DATA_NOT_FOUND,
                status_code=404,
            )
        return self._match_service.resolve_by_id(envelope_id, product)

    def validate_for_product(self, envelope_id: str, product_id: str) -> Match:
        return self.match(envelope_id, product_id)

    def resolve(
        self, candidate: dict[str, object], product_id: str, mode: str | None = None
    ) -> Match:
        del mode
        product = self.data_loader.get_product(product_id)
        if product is None:
            raise PortoError(
                f"Product not found: {product_id}",
                PortoErrorCode.PORTO_DATA_NOT_FOUND,
                status_code=404,
            )
        kind = str(candidate.get("kind", "by_id"))
        if kind == "by_dimensions":
            return self._match_service.resolve_by_dimensions(
                int(candidate.get("width", candidate.get("width_mm"))),  # type: ignore[call-overload]
                int(candidate.get("height", candidate.get("height_mm"))),  # type: ignore[call-overload]
                product,
            )
        envelope_id = str(candidate.get("envelope_id") or candidate.get("envelopeId") or "")
        return self._match_service.resolve_by_id(envelope_id, product)

    def _require_envelope(self, envelope_id: str) -> PortoEnvelope:
        envelope = self.data_loader.get_envelope(envelope_id)
        if envelope is None:
            raise PortoError(
                f"Envelope not found: {envelope_id}",
                PortoErrorCode.PORTO_DATA_NOT_FOUND,
                status_code=404,
            )
        return envelope

    def _window_rect(self, envelope_id: str, jurisdiction: str | None) -> EnvelopeRect | None:
        if not jurisdiction:
            return None
        layout = self.data_loader.get_layout(jurisdiction, envelope_id)
        if layout is None or not layout.window_supported or layout.window_area is None:
            return None
        area = layout.window_area
        return EnvelopeRect(x=area.x, y=area.y, width=area.width, height=area.height)

    def _layout_mark(
        self,
        *,
        envelope_id: str | None,
        product_id: str | None,
        zone_id: str | None,
        service_ids: builtins.list[str] | None,
    ) -> EnvelopeMarkFact | None:
        profile_id = self._binding.resolve_mark_profile_id(
            zone_id=zone_id,
            service_ids=service_ids,
        )
        profile = (
            self.data_loader.get_mark_profile(profile_id)
            if profile_id
            else self.data_loader.get_default_mark_profile()
        )
        if profile is None:
            return None
        placement = None
        if envelope_id:
            raw_placement = self.data_loader.get_mark_placement(envelope_id)
            if raw_placement is not None:
                placement = EnvelopeRect(
                    x=raw_placement.x,
                    y=raw_placement.y,
                    width=raw_placement.width,
                    height=raw_placement.height,
                )
        return EnvelopeMarkFact(
            type=profile.mark_type,
            size=EnvelopeSize(width=profile.width, height=profile.height),
            profile_id=profile.id,
            clearance=profile.clearance,
            placement=placement,
        )

    def _get_envelope_format_map(self) -> dict[str, dict[str, float]]:
        result: dict[str, dict[str, float]] = {}
        for envelope in self.data_loader.list_envelopes():
            short_edge = min(envelope.width, envelope.height)
            long_edge = max(envelope.width, envelope.height)
            result[envelope.id.upper()] = {
                "length": float(short_edge),
                "width": float(long_edge),
                "height": 5.0,
            }
        if result:
            return result
        for raw in self.data_loader.get_all_dimensions():
            dimension_id = str(raw.get("id", "")).strip().upper()
            normalized = self._normalize_data_dimension(raw)
            if not dimension_id or normalized is None:
                continue
            result[dimension_id] = normalized
        return result

    def _normalize_data_dimension(self, raw: dict[str, Any]) -> dict[str, float] | None:
        size = raw.get("size")
        if not isinstance(size, dict):
            return None
        width = size.get("width")
        height = size.get("height")
        thickness = size.get("thickness")
        if width is None or height is None or thickness is None:
            return None
        try:
            width_value = float(width)
            height_value = float(height)
            thickness_value = float(thickness)
        except (TypeError, ValueError):
            return None

        short_edge = min(width_value, height_value)
        long_edge = max(width_value, height_value)
        return {
            "length": short_edge,
            "width": long_edge,
            "height": thickness_value,
        }
