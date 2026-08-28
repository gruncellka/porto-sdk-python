"""Catalog package-version gate."""

from __future__ import annotations

import pytest

from porto_sdk.data.catalog_schema import (
    SUPPORTED_PORTO_DATA_VERSION_MAX_EXCLUSIVE,
    SUPPORTED_PORTO_DATA_VERSION_MIN,
    assert_catalog_schema_supported,
)
from porto_sdk.errors import ConfigurationError, PortoErrorCode


def test_accepts_supported_package_version() -> None:
    assert (
        assert_catalog_schema_supported({"project": {"version": SUPPORTED_PORTO_DATA_VERSION_MIN}})
        == SUPPORTED_PORTO_DATA_VERSION_MIN
    )


def test_rejects_missing_package_version() -> None:
    with pytest.raises(ConfigurationError) as exc:
        assert_catalog_schema_supported({})
    assert exc.value.code == PortoErrorCode.PORTO_DATA_INVALID


def test_rejects_malformed_package_version() -> None:
    with pytest.raises(ConfigurationError) as exc:
        assert_catalog_schema_supported({"project": {"version": "not-a-version"}})
    assert exc.value.code == PortoErrorCode.PORTO_DATA_INVALID


def test_rejects_older_package_version() -> None:
    with pytest.raises(ConfigurationError) as exc:
        assert_catalog_schema_supported({"project": {"version": "0.0.1"}})
    assert exc.value.code == PortoErrorCode.PORTO_DATA_TOO_OLD


def test_rejects_package_version_at_max_exclusive() -> None:
    with pytest.raises(ConfigurationError) as exc:
        assert_catalog_schema_supported(
            {"project": {"version": SUPPORTED_PORTO_DATA_VERSION_MAX_EXCLUSIVE}}
        )
    assert exc.value.code == PortoErrorCode.PORTO_DATA_TOO_NEW
