"""Declarative package-content contract for the Python SDK release artifacts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactContract:
    """Positive structure for wheel / sdist contents."""

    required_substrings: tuple[str, ...]
    """Paths that must appear (substring match against archive member names)."""

    forbidden_top_level: tuple[str, ...]
    """Top-level path segments that must never appear (universal repo junk)."""


FORBIDDEN_REPO = (
    ".env",
    "tests",
    "docs",
    ".github",
    ".cursor",
    "scripts",
    "artifacts",
    "labs",
)

# Wheel: porto_sdk/** + *.dist-info/**
WHEEL = ArtifactContract(
    required_substrings=(
        "porto_sdk/__init__.py",
        "porto_sdk/py.typed",
        ".dist-info/METADATA",
        ".dist-info/WHEEL",
    ),
    forbidden_top_level=FORBIDDEN_REPO,
)

# Sdist (paths relative to gruncellka_porto_sdk-VERSION/)
SDIST = ArtifactContract(
    required_substrings=(
        "porto_sdk/__init__.py",
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "PKG-INFO",
    ),
    forbidden_top_level=FORBIDDEN_REPO,
)

# Exact relative paths allowed at sdist root (besides porto_sdk/ and *.egg-info/)
SDIST_ALLOWED_ROOT_FILES = frozenset(
    {
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "PKG-INFO",
        # setuptools may emit a tiny generated setup.cfg into the sdist
        "setup.cfg",
        "MANIFEST.in",
    }
)
