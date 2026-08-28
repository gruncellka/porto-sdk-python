"""
DATAFACTORY API Adapter
"""

from datetime import datetime, timedelta
from typing import Any

from ..errors import PortoError, PortoErrorCode
from ..transport import HttpClient, Transport
from ..types import Address, ValidationResult


class DataFactoryAdapter:
    """Real DATAFACTORY API adapter"""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str = "https://api-eu.dhl.com/datafactory/autocomplete",
        client: Any | None = None,
        http_client: Transport | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url
        self.client = client
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._http_client: Transport = http_client or HttpClient()

    async def _authenticate(self) -> None:
        """Authenticate with DATAFACTORY API (OAuth 2.0)"""
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at:
                return

        response = await self._http_client.request(
            method="POST",
            url=f"{self.base_url}/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            idempotent=True,
        )

        if response.status_code != 200:
            raise PortoError(  # type: ignore[call-arg]
                "DATAFACTORY authentication failed",
                PortoErrorCode.PORTO_AUTH_FAILED,
                status_code=response.status_code,
                vendor="DATAFACTORY",
                retryable=True,
            )

        data = response.json()
        self._access_token = data.get("access_token")
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

    async def validate_address(self, address: Address) -> ValidationResult:
        """Validate address using DATAFACTORY API"""
        await self._authenticate()

        response = await self._http_client.request(
            method="POST",
            url=f"{self.base_url}/v2/validate",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._access_token}",
            },
            json={
                "name": address.name,
                "street": address.street,
                "houseNumber": address.house_number,
                "postalCode": address.postal_code,
                "city": address.locality,
                "countryCode": address.country_code,
                "regionCode": address.region_code,
            },
            idempotent=True,
        )

        if response.status_code != 200:
            raise PortoError(  # type: ignore[call-arg]
                "Address validation failed",
                PortoErrorCode.PORTO_MARK_INVALID,
                status_code=response.status_code,
                vendor="DATAFACTORY",
                retryable=response.status_code >= 500,
            )

        data = response.json()
        issues = data.get("issues", [])
        errors = [i.get("message", "") for i in issues if i.get("severity") == "error"]
        warnings = [i.get("message", "") for i in issues if i.get("severity") == "warning"]

        return ValidationResult(
            is_valid=data.get("isValid", False),
            errors=errors,
            warnings=warnings,
            data={
                "normalized": data.get("normalizedAddress"),
            }
            if data.get("normalizedAddress")
            else None,
        )

    async def validate(self, address: Address) -> ValidationResult:
        return await self.validate_address(address)


class OfflineDataFactoryAdapter:
    """Offline adapter - uses local validation only"""

    async def validate_address(self, address: Address) -> ValidationResult:
        """Basic local validation"""
        errors = []
        warnings = []  # type: ignore[var-annotated]

        if not address.name or not address.name.strip():
            errors.append("Address name is required")

        if not address.street or not address.street.strip():
            errors.append("Street is required")

        if not address.postal_code or not address.postal_code.isdigit():
            errors.append("Postal code must be numeric")

        if not address.country_code or len(address.country_code) != 2:
            errors.append("Country code must be 2 characters")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    async def validate(self, address: Address) -> ValidationResult:
        return await self.validate_address(address)
