"""
BDD test runner - ensures Python SDK implements all shared @sdk / @adapters features.

Loads feature files from gruncellka-porto-features package (or PORTO_FEATURES_PATH for dev).

Optional env (used by tests.bdd.runner):
  BDD_FEATURE_GLOB  — limit loaded feature files (relative to tree root)
  BDD_FEATURE_TREE  — "sdk" (default) or "adapters"
"""

from __future__ import annotations

import os
from fnmatch import fnmatch
from pathlib import Path

import pytest
from pytest_bdd import scenarios

from tests.support.porto_features_path import get_features_dir

pytestmark = pytest.mark.sdk_bdd


def _feature_tree() -> str:
    tree = os.environ.get("BDD_FEATURE_TREE", "sdk").strip().lower()
    if tree not in {"sdk", "adapters"}:
        raise SystemExit(f"BDD_FEATURE_TREE must be 'sdk' or 'adapters', got {tree!r}")
    return tree


def _required_tag(tree: str) -> str:
    return "@adapters" if tree == "adapters" else "@sdk"


def _has_required_tag(feature_file: Path, tag: str) -> bool:
    for line in feature_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == tag:
            return True
        if stripped.startswith("Feature:"):
            break
    return False


def _matches_batch_glob(feature_file: Path, features_dir: Path) -> bool:
    pattern = os.environ.get("BDD_FEATURE_GLOB", "").strip()
    if not pattern:
        return True
    rel = feature_file.relative_to(features_dir).as_posix()
    return fnmatch(rel, pattern)


TREE = _feature_tree()
FEATURES_DIR = get_features_dir() / TREE
REQUIRED_TAG = _required_tag(TREE)
for feature_file in sorted(FEATURES_DIR.rglob("*.feature")):
    if _has_required_tag(feature_file, REQUIRED_TAG) and _matches_batch_glob(
        feature_file, FEATURES_DIR
    ):
        scenarios(str(feature_file))
