import re
from pathlib import Path

from porto_sdk.services.execution_binding import ExecutionBinding
from porto_sdk.services.porto_execution import PortoExecution
from porto_sdk.services.porto_resolver import PortoResolver

_REPO = Path(__file__).resolve().parents[2]
_SERVICES = _REPO / "porto_sdk" / "services"
_TESTS = _REPO / "tests"


def test_porto_resolver_does_not_patch_service_tariffs():
    src = (_SERVICES / "porto_resolver.py").read_text(encoding="utf-8")
    assert "einschreiben" not in src
    assert "+105" not in src


def test_porto_resolver_does_not_resolve_wire_codes():
    src = (_SERVICES / "porto_resolver.py").read_text(encoding="utf-8")
    assert "resolve_wire_code(" not in src
    assert getattr(PortoResolver, "resolve_wire_code", None) is None


def test_execution_binding_does_not_import_product_resolver():
    src = (_SERVICES / "execution_binding.py").read_text(encoding="utf-8")
    assert "ProductResolver" not in src
    assert "PriceResolver" not in src


def test_execute_does_not_re_resolve():
    src = (_SERVICES / "porto_execution.py").read_text(encoding="utf-8")
    post_start = src.find("async def execute(")
    post_end = src.find("async def bytes(", post_start)
    post_body = src[post_start:post_end]
    assert "await self.resolve(" not in post_body
    assert "prepared.resolved_product" in post_body or "prepared.resolvedProduct" in post_body
    assert callable(getattr(PortoExecution, "execute", None))


def test_root_barrel_exports_public_client_surface():
    index = (_REPO / "porto_sdk" / "__init__.py").read_text(encoding="utf-8")
    assert "PortoClient" in index
    assert "ProviderClient" in index
    assert "EnvelopeIdentity" in index
    assert "Envelopes" in index
    assert "Envelope" in index
    assert "Restrictions" in index
    assert "LegalRestriction" in index
    assert "RoutingRestriction" in index
    assert "RestrictionImpact" in index
    assert "PortoMarkRequest" in index
    assert "Balance" in index
    for internal in (
        "load_internetmarke_config",
        "get_default_wire_id",
        "fetch_mark_bytes",
        "PortoResolver",
        "PortoExecution",
    ):
        assert internal not in index


def test_execution_binding_owns_wire_resolution():
    assert callable(ExecutionBinding.resolve_wire_code)


def test_canonical_execution_has_no_provider_voucher_layout():
    for rel in (
        "execution.py",
        "services/porto_resolver.py",
        "services/porto_execution.py",
        "services/mark_resolution.py",
    ):
        src = (_REPO / "porto_sdk" / rel).read_text(encoding="utf-8")
        assert "ADDRESS_ZONE" not in src
        assert "FRANKING_ZONE" not in src
        assert "MarkLayout" not in src
        assert "presentation" not in src


_RESOLVER_BYPASS_ALLOWLIST = {
    "client/test_clear_cache.py",
    "data/test_resolution_index.py",
    "resolution/test_quote.py",
}


def _iter_test_py() -> list[Path]:
    return sorted(path for path in _TESTS.rglob("*.py") if path.is_file())


def test_tests_do_not_bypass_via_private_resolver():
    violations: list[str] = []
    for path in _iter_test_py():
        rel = path.relative_to(_TESTS).as_posix()
        if rel in _RESOLVER_BYPASS_ALLOWLIST or rel.startswith("architecture/"):
            continue
        text = path.read_text(encoding="utf-8")
        if "._resolver" in text:
            violations.append(rel)
    assert violations == [], f"._resolver bypass outside allowlist: {violations}"


def test_generic_sdk_has_no_commerce_vocabulary():
    """Provider commerce terms stay adapter-private; core uses resolve/prepare/execute/mark."""
    core_roots = [
        _REPO / "porto_sdk" / "execution.py",
        _REPO / "porto_sdk" / "services",
        _REPO / "porto_sdk" / "provider_client.py",
        _REPO / "porto_sdk" / "__init__.py",
        _REPO / "porto_sdk" / "client.py",
        _REPO / "porto_sdk" / "adapters" / "protocols",
        _REPO / "porto_sdk" / "errors",
        _REPO / "porto_sdk" / "mark_content.py",
    ]
    for root in core_roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob("*.py")
        for path in paths:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(_REPO)
            lower = text.lower()
            assert "shoppingcart" not in lower, f"{rel} leaks shopping cart"
            assert "shopping_cart" not in lower, f"{rel} leaks shopping_cart"
            assert not re.search(r"\bcart\b", lower), f"{rel} leaks cart"
            assert not re.search(r"\bcheckout\b", lower), f"{rel} leaks checkout"
            assert not re.search(r"\bpurchase\b", lower), f"{rel} leaks purchase"
            assert "order_id" not in text, f"{rel} leaks order_id (use request_id)"
