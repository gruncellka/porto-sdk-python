"""
CLI argument validation. Single responsibility: required-flag checks.
"""

import argparse

from ._config_store import DEFAULT_PROVIDER


def missing_flags(args: argparse.Namespace, fields: list[tuple[str, str]]) -> list[str]:
    """List missing required flags."""
    missing: list[str] = []
    for field_name, flag in fields:
        value = getattr(args, field_name, None)
        if value is None or value == "":
            missing.append(flag)
    return missing


def ensure_required_flags(
    args: argparse.Namespace, command_name: str, fields: list[tuple[str, str]]
) -> None:
    """Raise ValueError if required flags are missing."""
    missing = missing_flags(args, fields)
    if missing:
        raise ValueError(f"Missing required options for '{command_name}': {', '.join(missing)}.")


def add_provider_flag(parser: argparse.ArgumentParser) -> None:
    """Add --provider flag to a subparser."""
    parser.add_argument(
        "--provider",
        help=f"Postal provider (e.g. deutschepost, swisspost). Default from config or {DEFAULT_PROVIDER}",
    )


def add_output_flags(parser: argparse.ArgumentParser) -> None:
    """Add --json and --pretty flags."""
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("--pretty", action="store_true", help="Human-readable output")
