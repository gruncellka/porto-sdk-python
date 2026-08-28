"""
Letter Validation Service

Implements SOLID principles:
- Single Responsibility: Handles letter validation only
- Open/Closed: Extensible via protocols/interfaces
- Dependency Inversion: Depends on abstractions (PortoResolver, PortoDataValidator)
"""

from ..data.domain_validator import DomainIds
from ..errors import PortoError, PortoErrorCode
from ..types import Address, Dimensions, ValidationResult
from .address import AddressResolver
from .porto_resolver import PortoResolver


class LetterValidationService:
    def __init__(
        self,
        resolver: PortoResolver,
        validator: DomainIds,
        address_service: AddressResolver,
    ):
        self.resolver = resolver
        self.validator = validator
        self.address_service = address_service

    async def validate_address(
        self,
        address: Address,
        check_sanctions: bool = True,
    ) -> ValidationResult:
        return await self.address_service.validate_address_with_sanctions(
            address,
            check_sanctions=check_sanctions,
        )

    async def validate_dimensions(self, dimensions: Dimensions) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        if dimensions.length < 1 or dimensions.width < 1:
            errors.append("Length and width must be positive")

        if dimensions.width > 0:
            aspect_ratio = dimensions.length / dimensions.width
            if aspect_ratio < 1.0 or aspect_ratio > 2.0:
                warnings.append(
                    f"Unusual aspect ratio ({aspect_ratio:.2f}); "
                    f"many letter formats are typically 1.0-2.0"
                )

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    def _find_products_by_dimensions(
        self,
        length: int,
        width: int,
        height: int,
        thickness: int | None = None,
    ) -> list:
        matching = []
        products = self.resolver.list_products()
        dimensions = self.resolver.list_dimensions()
        for dim in dimensions:
            size = dim.get("size", {})
            d_len = size.get("width", 0)
            d_width = size.get("height", 0)
            d_thick = size.get("thickness", 0)
            if (
                length <= d_len
                and width <= d_width
                and height <= d_thick
                and (thickness is None or thickness <= d_thick)
            ):
                dim_id = dim.get("id")
                for p in products:
                    if dim_id in getattr(p, "envelope_ids", []):
                        if p not in matching:
                            matching.append(p)
        return matching

    def _find_products_by_weight(self, weight: int) -> list:
        wt_id = self.resolver.weight_tier_resolver.resolve(weight)
        if not wt_id:
            return []
        zones = self.resolver.list_zones()
        matching = []
        for p in self.resolver.list_products():
            if any(
                self.resolver.product_resolver.is_valid_combination(p.id, zone.id, wt_id)
                for zone in zones
            ):
                matching.append(p)
        return matching

    def identify_candidate_products(self, dimensions: Dimensions, weight: int) -> list[str]:
        """Envelope-based identify: product ids matching dimensions + weight."""
        max_weight = self._max_weight()
        if weight > max_weight:
            raise PortoError(
                f"Weight {weight}g exceeds maximum {max_weight}g",
                PortoErrorCode.PORTO_TOO_HEAVY,
                status_code=400,
                details={"weight": weight, "max_weight": max_weight},
            )
        dimension_products = self._find_products_by_dimensions(
            dimensions.length,
            dimensions.width,
            dimensions.height,
            dimensions.thickness,
        )
        weight_products = self._find_products_by_weight(weight)
        dim_ids = {p.id for p in dimension_products}
        if dim_ids:
            return [p.id for p in weight_products if p.id in dim_ids] or [
                p.id for p in dimension_products
            ]
        return [p.id for p in weight_products]

    def _max_weight(self) -> int:
        tiers = self.resolver.list_weight_tiers()
        if not tiers:
            return 1000
        return max(tier.max_weight for tier in tiers)
