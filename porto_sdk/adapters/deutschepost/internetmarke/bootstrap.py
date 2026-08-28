"""
Internetmarke adapter bootstrap - reads provider-specific env, builds WireConfig.
Provider/wire specifics live here, not in generic config.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....config import WireConfig

DEFAULT_BASE_URL = "https://api-eu.dhl.com/post/de/shipping/im/v1"


def _get_env(
    provider: str,
    wire: str,
    field: str,
    env: dict[str, str] | None = None,
) -> str | None:
    e: dict[str, str] = dict(env) if env is not None else dict(os.environ)
    key = f"PORTO_{provider.upper()}_{wire.upper()}_{field}"
    return e.get(key)


def _get_integrator_api_credentials(
    provider: str,
    env: dict[str, str],
) -> tuple[str | None, str | None]:
    api_key = (
        _get_env(provider, "internetmarke", "API_KEY", env)
        or _get_env(provider, "internetmarke", "DHL_API_KEY", env)
        or env.get("DHL_API_KEY")
    )
    api_secret = (
        _get_env(provider, "internetmarke", "API_SECRET", env)
        or _get_env(provider, "internetmarke", "DHL_API_SECRET", env)
        or env.get("DHL_API_SECRET")
    )
    return api_key, api_secret


def load_internetmarke_config(
    provider: str,
    env: dict[str, str] | None = None,
) -> WireConfig | None:
    """
    Load Internetmarke wire config from env. Returns None without integrator
    API key/secret, so the wire stays unconfigured rather than half-credentialed.
    Env, first match wins: PORTO_DEUTSCHEPOST_INTERNETMARKE_*, then INTERNETMARKE_* / DHL_*.
    """
    e = dict(env) if env is not None else dict(os.environ)
    username = _get_env(provider, "internetmarke", "USERNAME", e) or e.get("INTERNETMARKE_USERNAME")
    password = _get_env(provider, "internetmarke", "PASSWORD", e) or e.get("INTERNETMARKE_PASSWORD")
    api_key, api_secret = _get_integrator_api_credentials(provider, e)
    if not api_key or not api_secret:
        return None

    base_url = (
        _get_env(provider, "internetmarke", "BASE_URL", e)
        or e.get("INTERNETMARKE_BASE_URL")
        or e.get("DHL_BASE_URL")
    )
    partner_id = _get_env(provider, "internetmarke", "PARTNER_ID", e) or e.get(
        "INTERNETMARKE_PARTNER_ID"
    )

    credentials: dict[str, str] = {
        "dhl_api_key": api_key,
        "dhl_api_secret": api_secret,
    }
    if username:
        credentials["username"] = username
    if password:
        credentials["password"] = password
    if partner_id:
        credentials["partner_id"] = partner_id

    from ....config import WireConfig

    return WireConfig(
        base_url=base_url.rstrip("/") if base_url else None,
        credentials=credentials,
    )


def get_internetmarke_base_url(
    wire_config: WireConfig | None,
) -> str:
    return (wire_config.base_url if wire_config else None) or DEFAULT_BASE_URL


def build_internetmarke_adapter(
    wires: dict[str, "WireConfig"] | None,
    env: dict[str, str] | None = None,
    *,
    provider: str = "deutschepost",
    http_client=None,
):
    """Assemble Internetmarke adapter. User credentials may be omitted until the call."""
    from .adapter import InternetmarkeAdapter

    im = (wires or {}).get("internetmarke")
    if im is None and env is not None:
        im = load_internetmarke_config(provider, env)
    creds = (im.credentials or {}) if im else {}
    return InternetmarkeAdapter(
        username=creds.get("username"),
        password=creds.get("password"),
        api_key=creds.get("dhl_api_key"),
        api_secret=creds.get("dhl_api_secret"),
        base_url=get_internetmarke_base_url(im),
        partner_id=creds.get("partner_id"),
        http_client=http_client,
    )
