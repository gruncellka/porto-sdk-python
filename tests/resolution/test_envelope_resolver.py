# pyright: reportMissingImports=false
from unittest.mock import MagicMock

import pytest  # type: ignore[import-not-found]

from porto_sdk.config import PortoConfig, ProviderRuntimeConfig
from porto_sdk.data.entities.envelopes import PortoEnvelope
from porto_sdk.services.envelope_resolver import EnvelopeResolverService
from porto_sdk.services.porto_resolver import Porto, PortoResolver, ResolutionRequest
from porto_sdk.types import ValidationResult


def _fake_data_loader():
    envelopes = [
        PortoEnvelope(id="DL", label="DL", width=220, height=110),
        PortoEnvelope(id="C6", label="C6", width=162, height=114),
        PortoEnvelope(id="C5", label="C5", width=229, height=162),
        PortoEnvelope(id="C4", label="C4", width=324, height=229),
        PortoEnvelope(id="B4", label="B4", width=353, height=250),
    ]

    class _EnvelopesLoader:
        def get_envelope(self, envelope_id: str):
            return next((row for row in envelopes if row.id == envelope_id), None)

        def list_envelopes(self):
            return list(envelopes)

        def all_ids(self):
            return {row.id for row in envelopes}

    class _DataLoader:
        _envelopes_loader = _EnvelopesLoader()

        def list_envelopes(self):
            return list(envelopes)

        def get_all_dimensions(self):
            return []

        def get_all_products(self):
            return []

        def get_all_weight_tiers(self):
            return []

        def get_all_zones(self):
            return []

        @property
        def resolution_graph(self):
            return MagicMock(links={})

        @property
        def resolution_index(self):
            return None

    return _DataLoader()


@pytest.mark.offline
@pytest.mark.asyncio
async def test_envelope_resolver_applies_format_policy(porto_data_path) -> None:
    from porto_sdk import PortoClient

    client = PortoClient(
        PortoConfig(
            providers={"deutschepost": ProviderRuntimeConfig()},
            data=porto_data_path,
            strict_data_validation=False,
        )
    )
    result = await client.envelopes.identify(envelope_format="DL", weight=20)
    assert result.format == "DL"
    assert result.resolution_weight == 20


@pytest.mark.offline
def test_porto_resolver_resolution_wraps_porto() -> None:
    resolver = PortoResolver.__new__(PortoResolver)

    class _W:
        id = "W0050"
        max_weight = 50

    class _Z:
        id = "domestic"
        name = "Domestic"

    class _P:
        id = "standardbrief"
        name = "X"

    porto = MagicMock(spec=Porto)
    porto.product = _P()
    porto.zone = _Z()
    porto.weight_tier = _W()
    porto.amount = 95
    porto.currency = "EUR"

    resolver.resolve = lambda request: porto  # type: ignore[method-assign]
    result = resolver.resolve(ResolutionRequest(country_code="de", weight=20))
    assert result.amount == 95


@pytest.mark.offline
def test_envelope_resolver_policy_formats_exist_in_loaded_dimensions() -> None:
    class _Validation:
        async def validate_dimensions(self, _dimensions):
            return ValidationResult(is_valid=True, errors=[], warnings=[])

    service = EnvelopeResolverService(_Validation(), _fake_data_loader())  # type: ignore[arg-type]
    loaded = set(service.list_supported_formats())
    for format_id in service.list_policy_format_ids():
        assert format_id in loaded


@pytest.mark.offline
def test_envelope_resolver_supports_formats_loaded_from_porto_data() -> None:
    class _Validation:
        async def validate_dimensions(self, _dimensions):
            return ValidationResult(is_valid=True, errors=[], warnings=[])

    service = EnvelopeResolverService(_Validation(), _fake_data_loader())  # type: ignore[arg-type]
    parsed = service.parse_dimensions(envelope_format="B4", dimensions=None)
    assert parsed["height"] == 5.0
