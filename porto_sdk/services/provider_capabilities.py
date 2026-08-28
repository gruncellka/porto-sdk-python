"""
Provider Capabilities Service - Policy Layer

Answers: "Can this provider use this feature under this context?"
This is NOT an adapter and NOT a resolver. It is a separate policy layer.

A service enables a feature iff services[].features[] resolves to that
Feature.kind. Unknown / missing → False (fail-closed).
Public can() takes FeatureKind only.
"""

from typing import TypedDict

from ..data.loader import PortoDataLoader
from ..kinds import FeatureKind, is_feature_kind, parse_feature_kind


class CapabilityContext(TypedDict, total=False):
    """Context for capability checks."""

    zone: str
    country_code: str
    wire: str


class ProviderCapabilitiesService:
    """Policy layer for feature availability per provider and context."""

    def __init__(self, loader: PortoDataLoader) -> None:
        self._loader = loader

    def can_use_feature(
        self,
        provider: str,
        feature: FeatureKind | str,
        context: CapabilityContext | None = None,
    ) -> bool:
        del provider
        if not is_feature_kind(feature):
            return False
        feat_kind = parse_feature_kind(feature)
        ctx = context or {}
        zone = (ctx.get("zone") or "").strip().lower()

        services_with_feature = []
        for svc in self._loader.get_all_services():
            for fid in svc.features:
                row = self._loader.get_feature(str(fid))
                if row is not None and row.kind == feat_kind:
                    services_with_feature.append(svc)
                    break

        if not services_with_feature:
            return False

        for svc in services_with_feature:
            if svc.supported_zones and zone and zone not in svc.supported_zones:
                continue
            return True

        return False

    def can(
        self,
        provider: str,
        feature: FeatureKind | str,
        context: CapabilityContext | None = None,
    ) -> bool:
        return self.can_use_feature(provider, feature, context)
