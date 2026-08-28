#!/usr/bin/env python3
"""Build inspect + clean-install smoke for the Python SDK wheel."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from artifact_contract import WHEEL  # noqa: E402

DIST_INFO_RE = re.compile(r"^[^/]+\.dist-info/")


def _python() -> str:
    venv = ROOT / ".venv" / "bin" / "python"
    if venv.is_file():
        return str(venv)
    return sys.executable


def _list_wheel(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as zf:
        return zf.namelist()


def _top_level(name: str) -> str:
    return name.split("/", 1)[0]


def check_wheel(names: list[str]) -> list[str]:
    errors: list[str] = []
    for req in WHEEL.required_substrings:
        if not any(req in n for n in names):
            errors.append(f"missing required content matching {req!r}")

    for name in names:
        if name.endswith("/"):
            continue
        if name.startswith("porto_sdk/"):
            continue
        if DIST_INFO_RE.match(name):
            continue
        errors.append(f"unexpected path {name!r}")

    for name in names:
        top = _top_level(name)
        if top in WHEEL.forbidden_top_level:
            errors.append(f"forbidden top-level {top!r} in {name!r}")
        parts = name.split("/")
        for part in parts:
            if part in ("tests", "docs", ".github", ".cursor", "scripts") and not name.startswith(
                "porto_sdk/"
            ):
                errors.append(f"repository path segment {part!r} in {name!r}")
                break

    return errors


def build_wheel(python: str) -> Path:
    dist = ROOT / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    subprocess.run([python, "-m", "pip", "install", "-q", "build"], cwd=ROOT, check=True)
    subprocess.run([python, "-m", "build", "--wheel"], cwd=ROOT, check=True)
    wheels = sorted(dist.glob("gruncellka_porto_sdk-*.whl"))
    if not wheels:
        raise SystemExit("no wheel produced in dist/")
    return wheels[-1]


def smoke_install(python: str, wheel: Path) -> None:
    smoke = ROOT / "artifact-smoke-py"
    if smoke.exists():
        shutil.rmtree(smoke)
    subprocess.run([python, "-m", "venv", str(smoke)], check=True)
    pip = smoke / "bin" / "pip"
    py = smoke / "bin" / "python"
    subprocess.run([str(pip), "install", "-q", "-U", "pip"], check=True)
    subprocess.run([str(pip), "install", "-q", str(wheel)], check=True)
    code = (
        "from porto_sdk import PortoClient, PortoConfig\n"
        "assert callable(PortoClient)\n"
        "cfg = PortoConfig()\n"
        "assert cfg is not None\n"
        "print('public import OK')\n"
    )
    subprocess.run([str(py), "-c", code], check=True)
    shutil.rmtree(smoke)


def main() -> int:
    python = _python()
    print("=== Build wheel ===")
    wheel = build_wheel(python)
    print(f"Wheel: {wheel}")

    print("=== Contract ===")
    names = _list_wheel(wheel)
    errors = check_wheel(names)
    if errors:
        print("Artifact contract failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("wheel matches ArtifactContract")

    print("=== Clean-env smoke ===")
    smoke_install(python, wheel)
    print("Artifact verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
