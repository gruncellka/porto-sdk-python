"""
Pytest configuration and fixtures for BDD tests
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from porto_sdk import PortoClient, PortoConfig
from tests.support.porto_features_path import get_fixtures_dir

pytest_plugins = [
    "tests.bdd.steps.config",
    "tests.bdd.steps.envelopes",
    "tests.bdd.steps.resolution",
    "tests.bdd.steps.products",
    "tests.bdd.steps.common",
    "tests.bdd.steps.assertions",
    "tests.bdd.steps.pricing",
    "tests.bdd.steps.data",
    "tests.bdd.steps.services",
    "tests.bdd.steps.restrictions",
    "tests.bdd.steps.validation",
    "tests.bdd.steps.errors",
    "tests.bdd.steps.marks",
]


# ═══════════════════════════════════════════════════════════════════════════
# PATH FIXTURES
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def data_path():
    """Get path to porto-data for BDD tests."""
    from tests.support.porto_features_path import get_porto_data_path

    return get_porto_data_path()


@pytest.fixture(scope="session")
def porto_data_path():
    """porto-data path for integration tests; skip when unavailable."""
    from tests.support.porto_features_path import get_porto_data_path

    try:
        return get_porto_data_path()
    except FileNotFoundError as exc:
        pytest.skip(str(exc))


@pytest.fixture(scope="session")
def fixtures_path():
    """Get path to shared test fixtures (from gruncellka-porto-features package or PORTO_FEATURES_PATH)"""
    return get_fixtures_dir()


# ═══════════════════════════════════════════════════════════════════════════
# CLIENT FIXTURES
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def client(data_path):
    """Create Porto SDK client"""
    return PortoClient(
        PortoConfig(
            data=data_path,
        )
    )


@pytest.fixture
def context():
    """Context for sharing data between steps"""
    return {}


# ═══════════════════════════════════════════════════════════════════════════
# ADDRESS FIXTURES
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def test_addresses(fixtures_path):
    """Load all test address fixtures"""
    addresses = {}
    addresses_dir = fixtures_path / "addresses"
    if addresses_dir.exists():
        for addr_file in addresses_dir.glob("*.json"):
            with open(addr_file) as f:
                data = json.load(f)
                addresses[data["id"]] = data
    return addresses


# ═══════════════════════════════════════════════════════════════════════════
# ARTIFACT RECORDING
# ═══════════════════════════════════════════════════════════════════════════


class ArtifactRecorder:
    """Records test artifacts for debugging and compliance"""

    def __init__(self, run_dir: Path, test_id: str):
        self.run_dir = run_dir
        self.test_id = test_id
        self.request_data: dict[str, Any] = {}
        self.response_data: dict[str, Any] = {}
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Ensure artifact directories exist"""
        for subdir in ["requests", "responses", "stamps", "errors"]:
            (self.run_dir / subdir).mkdir(parents=True, exist_ok=True)

    def record_sdk_input(self, data: dict):
        """Record SDK-level input (letter, address, etc.)"""
        self.request_data["sdk_input"] = data

    def record_pre_calculation(self, zone: str, price: int, product_code: str):
        """Record pre-calculated values from porto-data"""
        self.request_data["pre_calculated"] = {
            "zone": zone,
            "price_cents": price,
            "product_code": product_code,
        }

    def record_api_request(self, url: str, method: str, headers: dict, body: dict):
        """Record actual API request (redact sensitive data)"""
        safe_headers = {
            k: "[REDACTED]" if "auth" in k.lower() or "token" in k.lower() else v
            for k, v in headers.items()
        }
        self.request_data["api_request"] = {
            "url": url,
            "method": method,
            "headers": safe_headers,
            "body": body,
        }

    def record_api_response(
        self,
        status: int,
        headers: dict,
        body: dict,
        duration: float,
    ):
        """Record API response"""
        self.response_data = {
            "test_id": self.test_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "duration": duration,
            "http": {"status_code": status, "headers": dict(headers)},
            "api_response": body,
        }

    def record_validation(self, expected: int, actual: int):
        """Record price validation result"""
        self.response_data["validation"] = {
            "price_match": expected == actual,
            "expected_price": expected,
            "actual_price": actual,
            "difference": actual - expected,
        }

    def record_error(self, error_type: str, message: str, details: dict | None = None):
        """Record error for failed tests"""
        error_data = {
            "test_id": self.test_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error_type": error_type,
            "message": message,
            "details": details or {},
        }
        error_file = self.run_dir / "errors" / f"{self.test_id}.json"
        error_file.write_text(json.dumps(error_data, indent=2, default=str))

    def save(self):
        """Save all recorded artifacts"""
        if not self.request_data and not self.response_data:
            return

        self.request_data["test_id"] = self.test_id
        self.request_data["timestamp"] = datetime.utcnow().isoformat() + "Z"

        req_file = self.run_dir / "requests" / f"{self.test_id}.json"
        req_file.write_text(json.dumps(self.request_data, indent=2, default=str))

        if self.response_data:
            resp_file = self.run_dir / "responses" / f"{self.test_id}.json"
            resp_file.write_text(json.dumps(self.response_data, indent=2, default=str))


def get_artifacts_dir() -> Path:
    """Resolve artifacts directory (ARTIFACTS_DIR override or SDK-local default)."""
    if env_dir := os.environ.get("ARTIFACTS_DIR"):
        return Path(env_dir)
    return Path(__file__).parent.parent / "artifacts"


@pytest.fixture(scope="session")
def artifacts_run_dir():
    """Create and return the artifacts directory for this test run"""
    base_dir = get_artifacts_dir()
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
    env = "ci" if os.environ.get("CI") else "local"
    run_id = f"{timestamp}_{env}"

    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Create symlink to latest
    latest_link = base_dir / "latest"
    if latest_link.is_symlink():
        latest_link.unlink()
    try:
        latest_link.symlink_to(run_id)
    except OSError:
        pass  # Symlinks may not work on all systems

    # Write run metadata
    metadata = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "environment": env,
        "cwd": str(Path.cwd()),
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    return run_dir


@pytest.fixture
def artifact_recorder(request, artifacts_run_dir):
    """Provide artifact recorder for tests"""
    # Generate test ID from test name
    test_name = request.node.name
    # e.g., "test_api_stamp[STANDARD-DE-20]" → "STANDARD_DE_20"
    test_id = test_name.replace("[", "_").replace("]", "").replace("-", "_")

    recorder = ArtifactRecorder(artifacts_run_dir, test_id)
    yield recorder
    recorder.save()
