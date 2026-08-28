"""
Porto Data Validator - Validates against porto-data schemas
"""

from ..types import ValidationResult
from .loader import PortoDataLoader


class DomainIds:
    def __init__(self, loader: PortoDataLoader):
        self.loader = loader

    def get_product_ids(self) -> list[str]:
        """Get all valid product IDs from porto-data"""
        return [p.id for p in self.loader.get_all_products()]

    def get_zone_ids(self) -> list[str]:
        """Get all valid zone IDs from porto-data"""
        return [z.id for z in self.loader.get_all_zones()]

    def validate_product_id(self, product_id: str) -> ValidationResult:
        """Validate product_id (provider-native) exists in porto-data. Uses only get_product."""
        product = self.loader.get_product(product_id)
        if product:
            return ValidationResult(is_valid=True, errors=[], warnings=[])
        return ValidationResult(
            is_valid=False,
            errors=[f"Product {product_id} not found in porto-data"],
            warnings=[],
        )

    def validate_zone(self, zone_id: str) -> ValidationResult:
        """Validate zone ID exists in porto-data"""
        zone = self.loader.get_zone(zone_id)
        if not zone:
            return ValidationResult(
                is_valid=False,
                errors=[f"Zone {zone_id} not found in porto-data"],
                warnings=[],
            )
        return ValidationResult(is_valid=True, errors=[], warnings=[])

    def validate_country_code(self, country_code: str) -> ValidationResult:
        """Validate country code and resolve to zone"""
        zone = self.loader.get_zone_by_country_code(country_code)
        if not zone:
            return ValidationResult(
                is_valid=False,
                errors=[f"Country {country_code} not found in any zone"],
                warnings=[],
            )
        return ValidationResult(is_valid=True, errors=[], warnings=[], data={"zone": zone})

    def check_restrictions(self, country_code: str, product_id: str | None = None):
        """Check shipping restrictions for country code"""
        restriction = self.loader.check_restrictions(country_code, product_id)
        return {
            "is_allowed": restriction.is_allowed,
            "restrictions": restriction.restrictions,
            "warnings": restriction.warnings,
            "details": restriction.details,
        }
