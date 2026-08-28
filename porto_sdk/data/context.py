"""
Postal Resolution Context - Unified runtime object for multi-provider resolution

Holds loader (with global + provider data) and provider_id. The resolver uses
this context exclusively - no provider branching, all differences come from data.
"""

from dataclasses import dataclass

from .loader import PortoDataLoader


@dataclass
class PostalResolutionContext:
    """
    Unified resolution context: loader (global + provider data) + provider id.

    - loader: PortoDataLoader with global (dimensions, restrictions, features)
      and provider (products, prices, zones, weight_tiers, services, data_links)
    - provider_id: selected provider (deutschepost, swisspost)

    All provider differences come from the loaded data, not from resolver logic.
    """

    loader: PortoDataLoader
    provider_id: str
