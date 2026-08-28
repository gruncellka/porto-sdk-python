"""
Internetmarke Authentication Module

Handles authentication with Deutsche Post INTERNETMARKE REST API.
Uses single POST /user call per official spec (client_id, client_secret, username, password).
See: https://developer.dhl.com/api-reference/deutsche-post-internetmarke-post-paket-deutschland
"""

import logging
from datetime import datetime, timedelta

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore[assignment]

from ....errors import PortoError, PortoErrorCode
from ....transport import HttpClient, Transport
from .auth_errors import InternetmarkeAuthEndpoint, map_internetmarke_auth_http_error
from .utils import parse_wallet_balance_cents

DEFAULT_BASE_URL = "https://api-eu.dhl.com/post/de/shipping/im/v1"

logger = logging.getLogger(__name__)


class InternetmarkeAuth:
    """
    Authentication handler for Internetmarke REST API.

    Per official DHL spec: single POST /user with client_id, client_secret,
    username, password, grant_type (application/x-www-form-urlencoded).
    """

    def __init__(
        self,
        email: str,
        password: str,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        partner_id: str | None = None,
        http_client: Transport | None = None,
    ):
        if not HTTPX_AVAILABLE:
            raise ValueError("httpx is required for REST API. Install with: pip install httpx")

        self.api_key = api_key
        self.api_secret = api_secret
        self.email = email
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.partner_id = partner_id

        self._session_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._wallet_balance_cents: int | None = None
        self._http_client: Transport | None = http_client
        self._owns_http_client = http_client is None

    async def authenticate(self) -> None:
        """Authenticate with INTERNETMARKE REST API (single POST /user per official spec)."""
        if self._session_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at:
                return

        await self._authenticate_rest()

    async def _authenticate_rest(self) -> None:
        """
        POST /user with client_id, client_secret, username, password, grant_type.
        application/x-www-form-urlencoded per official spec.
        """
        try:
            if not HTTPX_AVAILABLE:
                raise ValueError("httpx is required for REST API")

            if not self._http_client:
                self._http_client = HttpClient()

            if not self.api_key or not self.api_secret:
                raise PortoError(
                    "DHL API client_id and client_secret are required for INTERNETMARKE auth",
                    PortoErrorCode.PORTO_AUTH_FAILED,
                    status_code=401,
                    provider="deutschepost",
                    wire="internetmarke",
                    retryable=False,
                )

            auth_url = f"{self.base_url}/user"
            body = {
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.api_secret,
                "username": self.email,
                "password": self.password,
            }

            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            if self.partner_id:
                headers["X-Partner-ID"] = self.partner_id

            logger.debug(f"Authenticating with REST API: {auth_url}")
            response = await self._http_client.request(
                method="POST",
                url=auth_url,
                data=body,
                headers=headers,
                idempotent=True,
            )

            if not response.is_success:
                error_text = response.text[:500]
                logger.error(f"REST authentication failed: {response.status_code} - {error_text}")
                auth_error = map_internetmarke_auth_http_error(
                    response.status_code,
                    error_text,
                    endpoint=InternetmarkeAuthEndpoint.COMBINED_USER,
                )
                details = auth_error.details()
                details["response_headers"] = dict(response.headers)
                raise PortoError(
                    auth_error.message,
                    auth_error.code,
                    status_code=response.status_code,
                    details=details,
                    provider="deutschepost",
                    wire="internetmarke",
                    retryable=auth_error.retryable,
                )

            auth_data = response.json()
            token = (
                auth_data.get("access_token")
                or auth_data.get("userToken")
                or auth_data.get("token")
            )
            if not token:
                raise PortoError(
                    "No access_token in INTERNETMARKE auth response",
                    PortoErrorCode.PORTO_AUTH_FAILED,
                    status_code=500,
                    details={"response_keys": list(auth_data.keys())},
                    provider="deutschepost",
                    wire="internetmarke",
                    retryable=False,
                )

            expires_in = auth_data.get("expires_in", 3000)
            self._session_token = token
            self._token_expires_at = datetime.now() + timedelta(seconds=int(expires_in))
            self._wallet_balance_cents = parse_wallet_balance_cents(auth_data)
            logger.info("REST authentication successful")

        except httpx.HTTPError as e:
            raise PortoError(
                f"INTERNETMARKE REST authentication network error: {e!s}",
                PortoErrorCode.PORTO_NETWORK_UNAVAILABLE,
                status_code=503,
                details={"error": str(e), "email": self.email},
                provider="deutschepost",
                wire="internetmarke",
                retryable=True,
            ) from e
        except PortoError:
            raise
        except Exception as e:
            raise PortoError(
                f"INTERNETMARKE REST authentication failed: {e!s}",
                PortoErrorCode.PORTO_AUTH_FAILED,
                status_code=401,
                details={"error": str(e), "email": self.email},
                provider="deutschepost",
                wire="internetmarke",
                retryable=True,
            ) from e

    def get_http_client(self) -> Transport | None:
        if not self._http_client:
            if not HTTPX_AVAILABLE:
                return None
            self._http_client = HttpClient()
        return self._http_client

    def get_token(self) -> str | None:
        return self._session_token

    def get_wallet_balance_cents(self) -> int | None:
        """Portokasse balance from last POST /user response (cents). No purchase required."""
        return self._wallet_balance_cents

    async def close(self) -> None:
        if self._owns_http_client and self._http_client:
            await self._http_client.close()
            self._http_client = None
