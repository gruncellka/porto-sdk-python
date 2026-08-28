#!/usr/bin/env python3
"""Verify this Python SDK's pyproject.toml uses registry package specs only."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

LOCAL_SPEC = re.compile(
    r"(^file:)|(^link:)|(^workspace:)|(@\s*file://)|(;\s*file://)",
    re.IGNORECASE,
)


def _is_local_spec(spec: str) -> bool:
    return bool(LOCAL_SPEC.search(spec.strip()))


def _dep_name(req: str) -> str:
    name = req.strip()
    for sep in ("@", ";", "[", ">", "<", "=", "!", "~", " "):
        if sep in name:
            name = name.split(sep, 1)[0]
    return name.strip().lower().replace("_", "-")


def check_pyproject(path: Path) -> list[str]:
    if not path.exists():
        return [f"{path}: missing pyproject.toml"]
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project") or {}
    errors: list[str] = []

    deps: list[str] = list(project.get("dependencies") or [])
    opt = project.get("optional-dependencies") or {}
    if isinstance(opt, dict):
        for group in opt.values():
            if isinstance(group, list):
                deps.extend(str(d) for d in group if isinstance(d, str))

    for dep in deps:
        if isinstance(dep, str) and _is_local_spec(dep):
            errors.append(f"{path}: local-source dependency {dep!r}")

    if project.get("name") == "gruncellka-porto-sdk":
        main_names = {_dep_name(d) for d in (project.get("dependencies") or []) if isinstance(d, str)}
        if "gruncellka-porto-data" not in main_names:
            errors.append(f"{path}: missing registry dependency gruncellka-porto-data")

    uv_sources = (data.get("tool") or {}).get("uv", {}).get("sources")
    if isinstance(uv_sources, dict) and uv_sources:
        errors.append(f"{path}: tool.uv.sources must be empty for release manifests")

    return errors


def run_check(root: Path) -> list[str]:
    return check_pyproject(root / "pyproject.toml")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify registry-only dependency manifests for the Python SDK."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="SDK root (default: cwd)")
    args = parser.parse_args(argv)
    errors = run_check(args.root.resolve())

    if errors:
        print("Registry check failed:\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            "\nCommitted manifests must declare porto packages as registry semver only.",
            file=sys.stderr,
        )
        return 1

    print("Registry check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
