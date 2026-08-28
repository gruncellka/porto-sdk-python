#!/usr/bin/env python3
"""Build once (sdist + wheel), assert ArtifactContract, clean-install smoke."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from artifact_contract import (  # noqa: E402
    SDIST,
    SDIST_ALLOWED_ROOT_FILES,
    WHEEL,
)

DIST_INFO_RE = re.compile(r"^[^/]+\.dist-info/")
SDIST_ROOT_RE = re.compile(r"^gruncellka_porto_sdk-[^/]+/")
EGG_INFO_RE = re.compile(r"^[^/]+\.egg-info(/|$)")


def _python() -> str:
    venv = ROOT / ".venv" / "bin" / "python"
    if venv.is_file():
        return str(venv)
    return sys.executable


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
        if name.endswith("/"):
            continue
        top = _top_level(name)
        if top in WHEEL.forbidden_top_level:
            errors.append(f"forbidden top-level {top!r} in {name!r}")
        for part in name.split("/"):
            if part in WHEEL.forbidden_top_level and not name.startswith("porto_sdk/"):
                errors.append(f"repository path segment {part!r} in {name!r}")
                break

    return errors


def _sdist_relative(name: str) -> str | None:
    m = SDIST_ROOT_RE.match(name)
    if not m:
        return None
    return name[m.end() :]


def check_sdist(names: list[str]) -> list[str]:
    errors: list[str] = []
    files = [n for n in names if not n.endswith("/")]
    rels: list[str] = []
    for name in files:
        rel = _sdist_relative(name)
        if rel is None:
            errors.append(f"unexpected archive root layout {name!r}")
            continue
        rels.append(rel)

    for req in SDIST.required_substrings:
        if not any(req in r for r in rels):
            errors.append(f"missing required content matching {req!r}")

    for rel in rels:
        if not rel:
            continue
        top = rel.split("/", 1)[0]
        if top in SDIST.forbidden_top_level:
            errors.append(f"forbidden top-level {top!r} in sdist path {rel!r}")
            continue
        if rel.startswith("porto_sdk/"):
            continue
        if EGG_INFO_RE.match(rel):
            continue
        if rel in SDIST_ALLOWED_ROOT_FILES:
            continue
        errors.append(f"unexpected sdist path {rel!r}")

    return errors


def build_artifacts(python: str) -> tuple[Path, Path]:
    dist = ROOT / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    subprocess.run([python, "-m", "pip", "install", "-q", "build"], cwd=ROOT, check=True)
    subprocess.run([python, "-m", "build"], cwd=ROOT, check=True)
    wheels = sorted(dist.glob("gruncellka_porto_sdk-*.whl"))
    sdists = sorted(dist.glob("gruncellka_porto_sdk-*.tar.gz"))
    if not wheels:
        raise SystemExit("no wheel produced in dist/")
    if not sdists:
        raise SystemExit("no sdist produced in dist/")
    return wheels[-1], sdists[-1]


def _list_wheel(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as zf:
        return zf.namelist()


def _list_sdist(sdist: Path) -> list[str]:
    with tarfile.open(sdist) as tf:
        # Files only — directory entries are not part of the content contract.
        return [m.name for m in tf.getmembers() if m.isfile()]


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
    porto = smoke / "bin" / "porto"
    if not porto.is_file():
        raise SystemExit("console script 'porto' missing after wheel install")
    subprocess.run([str(porto), "--help"], check=True, capture_output=True)
    meta = subprocess.run(
        [str(py), "-c", "import importlib.metadata as m; print(m.requires('gruncellka-porto-sdk'))"],
        check=True,
        capture_output=True,
        text=True,
    )
    if "gruncellka-porto-data" not in meta.stdout:
        raise SystemExit(
            f"runtime Requires-Dist missing gruncellka-porto-data: {meta.stdout!r}"
        )
    print("CLI entry point OK; Requires-Dist includes gruncellka-porto-data")
    shutil.rmtree(smoke)


def main() -> int:
    python = _python()
    print("=== Build sdist + wheel (single pass) ===")
    wheel, sdist = build_artifacts(python)
    print(f"Wheel: {wheel}")
    print(f"Sdist: {sdist}")

    print("=== Wheel contract ===")
    wheel_errors = check_wheel(_list_wheel(wheel))
    if wheel_errors:
        print("Wheel ArtifactContract failed:", file=sys.stderr)
        for err in wheel_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("wheel matches ArtifactContract")

    print("=== Sdist contract ===")
    sdist_errors = check_sdist(_list_sdist(sdist))
    if sdist_errors:
        print("Sdist ArtifactContract failed:", file=sys.stderr)
        for err in sdist_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("sdist matches ArtifactContract")

    print("=== Clean-env smoke ===")
    smoke_install(python, wheel)
    print("Artifact verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
