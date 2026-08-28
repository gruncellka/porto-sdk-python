"""Declarative package-content contract for the Python SDK release artifact."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactContract:
    """Positive structure for wheel / sdist contents."""

    required_substrings: tuple[str, ...]
    """Paths that must appear (substring match against archive member names)."""

    allowed_prefixes: tuple[str, ...]
    """Every archive member must start with one of these prefixes (after normalizing)."""

    forbidden_top_level: tuple[str, ...]
    """Top-level path segments that must never appear (universal repo junk)."""


# Wheel: porto_sdk/** + *.dist-info/**
# Sdist: gruncellka_porto_sdk-*/porto_sdk/** + metadata files
WHEEL = ArtifactContract(
    required_substrings=(
        "porto_sdk/__init__.py",
        ".dist-info/METADATA",
        ".dist-info/WHEEL",
    ),
    allowed_prefixes=(
        "porto_sdk/",
        # dist-info directory name varies with version
    ),
    forbidden_top_level=(
        ".env",
        "tests",
        "docs",
        ".github",
        ".cursor",
        "scripts",
        "artifacts",
        "labs",
    ),
)

SDIST = ArtifactContract(
    required_substrings=(
        "porto_sdk/__init__.py",
        "PKG-INFO",
        "pyproject.toml",
    ),
    allowed_prefixes=(),  # validated via allow-rules in verifier for sdist layout
    forbidden_top_level=(
        ".env",
        "tests",
        "docs",
        ".github",
        ".cursor",
        "scripts",
        "artifacts",
        "labs",
    ),
)
