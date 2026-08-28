"""Restrictions entity loader — policy/restrictions.json."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Collection, cast

from porto_sdk.errors.domains.data import raise_data_invalid

from .base import BaseEntityLoader

_JURISDICTIONS = frozenset({"EU", "CH", "UA"})
_COUNTRY_KEY = re.compile(r"^[A-Z]{2}$")
_REGION_KEY = re.compile(r"^[A-Z]{2}-[A-Z0-9]{1,3}$")


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _in_force(bounds: dict[str, Any], today: date) -> bool:
    start = _parse_date(bounds.get("effective_from"))
    end = _parse_date(bounds.get("effective_to"))
    if start and start > today:
        return False
    if end and end < today:
        return False
    return True


def _require_object(
    value: Any, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise_data_invalid(message, details=details)
    return value


def _require_text(value: Any, field: str, *, country: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise_data_invalid(
            f"restriction for {country} is missing {field}",
            details={"country_code": country, "field": field},
        )
    return value


def _normalize_instrument(raw: Any, *, country: str) -> dict[str, Any]:
    instrument = _require_object(
        raw,
        f"legal restriction for {country} has a non-object jurisdiction instrument",
        {"country_code": country},
    )
    if "impact" in instrument or "jurisdiction" in instrument:
        raise_data_invalid(
            f"legal restriction for {country} has an invalid jurisdiction instrument field",
            details={"country_code": country},
        )
    reference = instrument.get("reference")
    return {
        "reference": reference if isinstance(reference, str) else None,
        "effective_from": (
            instrument.get("effective_from")
            if isinstance(instrument.get("effective_from"), str)
            else None
        ),
        "effective_to": (
            instrument.get("effective_to")
            if isinstance(instrument.get("effective_to"), str)
            else None
        ),
    }


def _normalize_jurisdiction_map(raw: Any, *, country: str) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(raw, dict) or not raw:
        raise_data_invalid(
            f"legal restriction for {country} is missing jurisdictions",
            details={"country_code": country},
        )
    jurisdictions: dict[str, list[dict[str, Any]]] = {}
    for key, instruments in raw.items():
        if key not in _JURISDICTIONS:
            raise_data_invalid(
                f"legal restriction for {country} has an unknown jurisdiction",
                details={"country_code": country, "jurisdiction": key},
            )
        if not isinstance(instruments, list) or not instruments:
            raise_data_invalid(
                f"legal restriction for {country} is missing jurisdictions",
                details={"country_code": country, "jurisdiction": key},
            )
        jurisdictions[str(key)] = [
            _normalize_instrument(item, country=country) for item in instruments
        ]
    return jurisdictions


def _normalize_legal_regions(raw: Any, *, country: str) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict) or not raw:
        raise_data_invalid(
            f"legal restriction for {country} is missing regions",
            details={"country_code": country},
        )
    regions: dict[str, dict[str, Any]] = {}
    for code, payload in raw.items():
        if not isinstance(code, str) or not _REGION_KEY.match(code):
            raise_data_invalid(
                f"legal restriction for {country} has an invalid region key",
                details={"country_code": country},
            )
        region = _require_object(
            payload,
            f"legal restriction for {country} has a non-object region",
            {"country_code": country},
        )
        if "frameworks" in region:
            raise_data_invalid(
                f"legal restriction for {country} must use jurisdictions, not frameworks",
                details={"country_code": country, "region_code": code},
            )
        if "region_code" in region or "jurisdiction" in region:
            raise_data_invalid(
                f"legal restriction for {country} has an invalid region field",
                details={"country_code": country, "region_code": code},
            )
        normalized: dict[str, Any] = {
            "jurisdictions": _normalize_jurisdiction_map(
                region.get("jurisdictions"), country=country
            ),
            "reason": _require_text(region.get("reason"), "reason", country=country),
            "description": _require_text(region.get("description"), "description", country=country),
        }
        if "partial" in region:
            if region.get("partial") is not True:
                raise_data_invalid(
                    f"restriction for {country} has invalid region partial",
                    details={"country_code": country, "region_code": code},
                )
            normalized["partial"] = True
        regions[code] = normalized
    return regions


def _normalize_geo_regions(raw: Any, *, country: str, collection: str = "routing") -> dict[str, dict[str, Any]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise_data_invalid(
            f"{collection} restriction for {country} has a non-object regions",
            details={"country_code": country},
        )
    regions: dict[str, dict[str, Any]] = {}
    for code, payload in raw.items():
        if not isinstance(code, str) or not _REGION_KEY.match(code):
            raise_data_invalid(
                f"{collection} restriction for {country} has an invalid region key",
                details={"country_code": country},
            )
        region = _require_object(
            payload if payload is not None else {},
            f"{collection} restriction for {country} has a non-object region",
            {"country_code": country},
        )
        if (
            "frameworks" in region
            or "jurisdictions" in region
            or "region_code" in region
        ):
            raise_data_invalid(
                f"{collection} restriction for {country} has an invalid region field",
                details={"country_code": country, "region_code": code},
            )
        normalized: dict[str, Any] = {}
        if "partial" in region:
            if region.get("partial") is not True:
                raise_data_invalid(
                    f"restriction for {country} has invalid region partial",
                    details={"country_code": country, "region_code": code},
                )
            normalized["partial"] = True
        regions[code] = normalized
    return regions


def _normalize_legal(country: str, item: dict[str, Any]) -> dict[str, Any]:
    if "country_code" in item:
        raise_data_invalid(
            f"legal restriction for {country} must not have country_code",
            details={"country_code": country},
        )
    if "frameworks" in item:
        raise_data_invalid(
            f"legal restriction for {country} must use jurisdictions, not frameworks",
            details={"country_code": country},
        )
    if "regions" in item:
        if "jurisdictions" in item:
            raise_data_invalid(
                f"legal restriction for {country} must not mix country jurisdictions with regions",
                details={"country_code": country},
            )
        return {"regions": _normalize_legal_regions(item.get("regions"), country=country)}
    return {
        "jurisdictions": _normalize_jurisdiction_map(item.get("jurisdictions"), country=country),
        "reason": _require_text(item.get("reason"), "reason", country=country),
        "description": _require_text(item.get("description"), "description", country=country),
    }


def _normalize_routing(country: str, item: dict[str, Any]) -> dict[str, Any]:
    if "frameworks" in item or "jurisdictions" in item or "country_code" in item:
        raise_data_invalid(
            f"routing restriction for {country} must not have jurisdictions",
            details={"country_code": country},
        )
    payload: dict[str, Any] = {
        "authority": _require_text(item.get("authority"), "authority", country=country),
        "reference": _require_text(item.get("reference"), "reference", country=country),
        "reason": _require_text(item.get("reason"), "reason", country=country),
        "description": _require_text(item.get("description"), "description", country=country),
    }
    regions = _normalize_geo_regions(item.get("regions"), country=country, collection="routing")
    if regions:
        payload["regions"] = regions
    return payload


_NORMALIZERS = {
    "legal": _normalize_legal,
    "routing": _normalize_routing,
}


def _load_country_map(raw: Any, name: str) -> dict[str, dict[str, Any]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise_data_invalid(f"restrictions.json {name} must be an object keyed by country")
    if name not in _NORMALIZERS:
        raise_data_invalid(f"restrictions.json has unknown collection {name}")
    loaded: dict[str, dict[str, Any]] = {}
    for country, payload in raw.items():
        if not isinstance(country, str) or not _COUNTRY_KEY.match(country):
            raise_data_invalid(f"restrictions.json {name} has an invalid country key")
        row = _require_object(
            payload,
            f"restrictions {name}.{country} must be an object",
            {"country_code": country},
        )
        loaded[country] = _NORMALIZERS[name](country, row)
    return loaded


def remaining_jurisdiction_map(
    jurisdictions: dict[str, list[dict[str, Any]]],
    *,
    provider_jurisdictions: Collection[str] | None,
    today: date,
) -> dict[str, list[dict[str, Any]]]:
    tokens = (
        None
        if provider_jurisdictions is None
        else {str(token).upper() for token in provider_jurisdictions}
    )
    remaining: dict[str, list[dict[str, Any]]] = {}
    for key, instruments in jurisdictions.items():
        jurisdiction = str(key).upper()
        if tokens is not None and jurisdiction not in tokens:
            continue
        kept = [item for item in instruments if isinstance(item, dict) and _in_force(item, today)]
        if kept:
            remaining[jurisdiction] = kept
    return remaining


def _select_legal(
    payload: dict[str, Any],
    *,
    region_code: str | None,
    jurisdictions: Collection[str] | None,
    today: date,
) -> dict[str, Any] | None:
    regions = payload.get("regions") if isinstance(payload.get("regions"), dict) else {}
    if regions:
        if region_code and region_code not in regions:
            return None
        candidates = {region_code: regions[region_code]} if region_code else regions
        selected: dict[str, dict[str, Any]] = {}
        for code, region in candidates.items():
            if not isinstance(region, dict):
                continue
            raw_jurisdictions = region.get("jurisdictions")
            remaining = remaining_jurisdiction_map(
                cast(dict[str, list[dict[str, Any]]], raw_jurisdictions)
                if isinstance(raw_jurisdictions, dict)
                else {},
                provider_jurisdictions=jurisdictions,
                today=today,
            )
            if not remaining:
                continue
            projected = dict(region)
            projected["jurisdictions"] = remaining
            selected[code] = projected
        if not selected:
            return None
        return {"regions": selected}
    raw_jurisdictions = payload.get("jurisdictions")
    remaining = remaining_jurisdiction_map(
        cast(dict[str, list[dict[str, Any]]], raw_jurisdictions)
        if isinstance(raw_jurisdictions, dict)
        else {},
        provider_jurisdictions=jurisdictions,
        today=today,
    )
    if not remaining:
        return None
    projected = dict(payload)
    projected["jurisdictions"] = remaining
    projected.pop("regions", None)
    return projected


def _select_geo(payload: dict[str, Any], *, region_code: str | None) -> dict[str, Any] | None:
    regions = payload.get("regions") if isinstance(payload.get("regions"), dict) else {}
    if not regions:
        return dict(payload)
    if region_code:
        if region_code not in regions:
            return None
        projected = dict(payload)
        projected["regions"] = {region_code: dict(regions[region_code])}
        return projected
    projected = dict(payload)
    projected["regions"] = {code: dict(region) for code, region in regions.items()}
    return projected


@dataclass
class PostageRestriction:
    """Internal residue for address/validation paths. Not a public type."""

    is_allowed: bool
    restrictions: list[str]
    warnings: list[str]
    details: dict[str, Any] | None = None
    restriction: dict[str, Any] | None = None


class RestrictionsLoader(BaseEntityLoader):
    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._legal: dict[str, dict[str, Any]] = {}
        self._routing: dict[str, dict[str, Any]] = {}
        self._policy_raw: dict[str, Any] = {}

    def load(self, data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise_data_invalid("restrictions.json must be an object")
        if "operational" in data:
            raise_data_invalid("restrictions.json must not contain operational")
        self._policy_raw = data
        self._legal = _load_country_map(data.get("legal"), "legal")
        self._routing = _load_country_map(data.get("routing"), "routing")

    def get_policy_raw(self) -> dict[str, Any]:
        return self._policy_raw

    def get_data(self) -> dict[str, dict[str, dict[str, Any]]]:
        return {
            "legal": self._legal,
            "routing": self._routing,
        }

    def legal_catalog(self) -> dict[str, dict[str, Any]]:
        return self._legal

    def routing_catalog(self) -> dict[str, dict[str, Any]]:
        return self._routing

    def classify_restrictions(
        self,
        country_code: str,
        region_code: str | None = None,
        *,
        jurisdictions: Collection[str] | None = None,
        as_of: date | None = None,
    ) -> dict[str, dict[str, dict[str, Any]]]:
        today = as_of or datetime.now(UTC).date()
        normalized_country = str(country_code).upper()
        normalized_region = region_code.upper() if region_code else None
        selected: dict[str, dict[str, dict[str, Any]]] = {
            "legal": {},
            "routing": {},
        }
        legal = self._legal.get(normalized_country)
        if legal is not None:
            projected = _select_legal(
                legal,
                region_code=normalized_region,
                jurisdictions=jurisdictions,
                today=today,
            )
            if projected is not None:
                selected["legal"][normalized_country] = projected
        routing = self._routing.get(normalized_country)
        if routing is not None:
            projected = _select_geo(routing, region_code=normalized_region)
            if projected is not None:
                selected["routing"][normalized_country] = projected
        return selected

    def check_restrictions(
        self,
        country_code: str,
        product_id: str | None = None,
        zone_id: str | None = None,
        region_code: str | None = None,
        *,
        jurisdictions: Collection[str] | None = None,
        as_of: date | None = None,
    ) -> PostageRestriction:
        _ = product_id
        _ = zone_id
        _ = country_code
        _ = region_code
        _ = jurisdictions
        _ = as_of
        return PostageRestriction(is_allowed=True, restrictions=[], warnings=[])

    def get_restrictions_for_country(self, country_code: str) -> list[dict[str, Any]]:
        code = str(country_code).upper()
        rows: list[dict[str, Any]] = []
        for name, block in (
            ("legal", self._legal),
            ("routing", self._routing),
        ):
            payload = block.get(code)
            if payload is not None:
                rows.append({"collection": name, "country_code": code, **payload})
        return rows
