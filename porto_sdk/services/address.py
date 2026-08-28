"""
AddressResolver — jurisdiction address forms + sanctions / external formats.

Public accessor remains ``client.address``. Format failures populate
``ValidationResult``; mark prepare raises role-specific ``PORTO_ADDRESS_*`` codes.
"""

from __future__ import annotations

from typing import Any

from ..data.domain_validator import DomainIds
from ..data.loader import PortoDataLoader
from ..types import Address, ValidationResult

# Catalog required field names → Address attribute
_FIELD_ATTR = {
    "name": "name",
    "street": "street",
    "house_number": "house_number",
    "post_box": "post_box",
    "postal_code": "postal_code",
    "locality": "locality",
    "country_code": "country_code",
    "region_code": "region_code",
}

_LINE_FIELDS = ("name", "street", "house_number", "post_box", "postal_code", "locality")


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


class AddressResolver:
    """Validate addresses against jurisdiction forms from formats/addresses.json."""

    def __init__(
        self,
        data_loader: PortoDataLoader,
        validator: DomainIds,
    ):
        self.data_loader = data_loader
        self.validator = validator

    async def validate(
        self,
        address: Address,
        check_sanctions: bool = True,
    ) -> ValidationResult:
        """Validate address (sanctions optional). Preferred public name: client.address.validate."""
        return await self.validate_address_with_sanctions(address, check_sanctions=check_sanctions)

    async def validate_address_with_sanctions(
        self,
        address: Address,
        check_sanctions: bool = True,
    ) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        data: dict[str, Any] = {}

        basic_validation = await self._validate_address_basic(address)
        if not basic_validation.is_valid:
            errors.extend(basic_validation.errors)
        warnings.extend(basic_validation.warnings)
        if basic_validation.data:
            data.update(basic_validation.data)

        if address.region_code:
            region_validation = await self._validate_region_code(
                address.country_code, address.region_code
            )
            if not region_validation.is_valid:
                warnings.extend(region_validation.errors)
            if region_validation.warnings:
                warnings.extend(region_validation.warnings)
            if region_validation.data:
                data["region"] = region_validation.data

        del check_sanctions

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            data=data if data else None,
        )

    async def _validate_address_basic(self, address: Address) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        data: dict[str, Any] = {}

        country_validation = self.validator.validate_country_code(address.country_code)
        if not country_validation.is_valid:
            errors.extend(country_validation.errors)

        jurisdiction = address.country_code.upper()
        catalog = self.data_loader.get_address_form(jurisdiction)
        if catalog is None:
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
            )

        form_issues: list[dict[str, str]] = []
        has_post_box = _has_text(address.post_box)
        has_street_line = _has_text(address.street) or _has_text(address.house_number)

        if has_post_box and has_street_line:
            form_issues.append(
                {
                    "field": "post_box",
                    "code": "xor",
                    "jurisdiction": jurisdiction,
                    "kind": "post_box",
                }
            )
            errors.append(
                f"post_box: cannot combine with street/house_number for jurisdiction {jurisdiction}"
            )

        kind = "post_box" if has_post_box else "street"
        form_kind = catalog.get_kind(kind)
        if form_kind is None:
            form_issues.append(
                {
                    "field": "post_box" if kind == "post_box" else "street",
                    "code": "unsupported_kind",
                    "jurisdiction": jurisdiction,
                    "kind": kind,
                }
            )
            errors.append(f"{kind}: form kind not available for jurisdiction {jurisdiction}")
        else:
            for field_name in form_kind.required:
                attr = _FIELD_ATTR.get(field_name)
                if attr is None:
                    continue
                value = getattr(address, attr, None)
                missing = not value if field_name == "country_code" else not _has_text(value)
                if missing:
                    form_issues.append(
                        {
                            "field": field_name,
                            "code": "required",
                            "jurisdiction": jurisdiction,
                            "kind": kind,
                        }
                    )
                    errors.append(
                        f"{field_name}: required for {kind} form in jurisdiction {jurisdiction}"
                    )

        if not catalog.postal_code_re().fullmatch(address.postal_code or ""):
            form_issues.append(
                {
                    "field": "postal_code",
                    "code": "pattern",
                    "jurisdiction": jurisdiction,
                    "kind": kind,
                }
            )
            errors.append(f"postal_code: does not match pattern for jurisdiction {jurisdiction}")

        if catalog.max_line_length is not None:
            limit = catalog.max_line_length
            for field_name in _LINE_FIELDS:
                attr = _FIELD_ATTR[field_name]
                value = getattr(address, attr, None)
                if isinstance(value, str) and len(value) > limit:
                    form_issues.append(
                        {
                            "field": field_name,
                            "code": "max_line_length",
                            "jurisdiction": jurisdiction,
                            "kind": kind,
                        }
                    )
                    errors.append(
                        f"{field_name}: exceeds max_line_length {limit} "
                        f"for jurisdiction {jurisdiction}"
                    )

        if form_issues:
            data["form_issues"] = form_issues
            data["jurisdiction"] = jurisdiction
            data["standard"] = catalog.standard
            data["kind"] = kind

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            data=data if data else None,
        )

    async def _validate_region_code(self, country_code: str, region_code: str) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        data: dict[str, Any] = {}

        if "-" in region_code:
            parts = region_code.split("-", 1)
            if len(parts) == 2:
                region_country = parts[0].upper()
                region_sub = parts[1].upper()
                if region_country != country_code:
                    warnings.append(
                        f"Region code country ({region_country}) doesn't match "
                        f"address country ({country_code})"
                    )
                data["region_format"] = "iso_3166_2"
                data["region_country"] = region_country
                data["region_subdivision"] = region_sub
            else:
                warnings.append("Region code format unclear. Expected ISO 3166-2 format (CC-RR)")
        else:
            data["region_format"] = "simple"
            data["region_code"] = region_code.upper()
            warnings.append(
                "Region code format not ISO 3166-2. For better compatibility with "
                "external APIs, use ISO 3166-2 format (e.g., 'DE-BE' for Berlin, Germany)"
            )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            data=data if data else None,
        )

    async def _check_sanctions(self, address: Address) -> dict[str, Any] | None:
        zone = self.data_loader.get_zone_by_country_code(address.country_code)
        zone_id = zone.id if zone else None

        restriction = self.data_loader.check_restrictions(
            address.country_code,
            None,
            zone_id,
            address.region_code,
        )

        if not restriction.is_allowed or restriction.restrictions or restriction.warnings:
            return {
                "status": (restriction.restriction or {}).get("status"),
                "is_allowed": restriction.is_allowed,
                "is_restricted": not restriction.is_allowed,
                "restrictions": restriction.restrictions,
                "warnings": restriction.warnings,
                "reason": (
                    restriction.restrictions[0]
                    if restriction.restrictions
                    else restriction.warnings[0]
                    if restriction.warnings
                    else None
                ),
                "details": restriction.details,
            }

        return None

    def to_google_maps_format(self, address: Address) -> dict[str, Any]:
        return {
            "street_number": address.house_number,
            "route": address.street,
            "locality": address.locality,
            "postal_code": address.postal_code,
            "country": address.country_code,
            "administrative_area_level_1": address.region_code or None,
            "formatted_address": self._format_address(address),
        }

    def from_google_maps_format(self, google_address: dict[str, Any]) -> Address:
        components = google_address.get("address_components", [])

        def get_component(type_name: str, short: bool = False) -> str | None:
            for comp in components:
                types = comp.get("types", [])
                if type_name in types:
                    return comp.get("short_name" if short else "long_name")  # type: ignore[no-any-return]
            return None

        street_number = get_component("street_number")
        route = get_component("route")
        locality = get_component("locality")
        postal_code = get_component("postal_code")
        country = get_component("country", short=True)
        region = get_component("administrative_area_level_1", short=True)

        street_parts = []
        if street_number:
            street_parts.append(street_number)
        if route:
            street_parts.append(route)
        street = " ".join(street_parts) if street_parts else route or ""

        if not locality or not postal_code or not country:
            raise ValueError("Missing required address fields from Google Maps format")

        name = google_address.get("name") or google_address.get("formatted_address", "")

        return Address(
            name=name[:100],
            street=street[:100] if street else locality[:100],
            house_number=street_number or "1",
            postal_code=postal_code,
            locality=locality,
            country_code=country,
            region_code=region,
        )

    def to_postal_api_format(self, address: Address) -> dict[str, Any]:
        if address.post_box:
            line1 = f"PO Box {address.post_box}"
        else:
            line1 = f"{address.street or ''} {address.house_number or ''}".strip()
        return {
            "name": address.name,
            "address_line1": line1,
            "city": address.locality,
            "postal_code": address.postal_code,
            "state_province": address.region_code,
            "country": address.country_code,
        }

    def from_postal_api_format(self, postal_address: dict[str, Any]) -> Address:
        address_line1 = postal_address.get("address_line1", "")
        parts = address_line1.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].isdigit():
            street = parts[0]
            house_number = parts[1]
        else:
            street = address_line1
            house_number = postal_address.get("house_number", "1")

        return Address(
            name=postal_address.get("name", "")[:100],
            street=street[:100],
            house_number=house_number[:10],
            postal_code=postal_address.get("postal_code", ""),
            locality=postal_address.get("city", ""),
            country_code=postal_address.get("country", ""),
            region_code=postal_address.get("state_province"),
        )

    def _format_address(self, address: Address) -> str:
        if address.post_box:
            line = f"PO Box {address.post_box}"
        else:
            line = f"{address.street or ''} {address.house_number or ''}".strip()
        parts = [line, address.postal_code, address.locality]
        if address.region_code:
            parts.append(address.region_code)
        parts.append(address.country_code)
        return ", ".join(p for p in parts if p)
