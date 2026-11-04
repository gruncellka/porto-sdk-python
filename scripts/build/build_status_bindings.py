#!/usr/bin/env python3
"""Generate porto_sdk/statuses.py from porto-features statuses.json.

Sole SoT for public PortoStatus wire values: porto_features/statuses.json codes[].

Usage:
  python scripts/build/build_status_bindings.py          # write
  python scripts/build/build_status_bindings.py --check  # fail on drift

Missing statuses.json (published porto-features before the catalog ships)
is a soft skip so CI can still run bindings against the registry package.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _resolve_statuses_json() -> Path | None:
    env_path = os.environ.get("PORTO_FEATURES_PATH")
    if env_path:
        root = Path(env_path).expanduser().resolve()
        for candidate in (root / "statuses.json", root / "porto_features" / "statuses.json"):
            if candidate.is_file():
                return candidate
        return None

    for module_name in ("gruncellka_porto_features", "porto_features"):
        try:
            pkg = __import__(module_name)
        except ImportError:
            continue
        pkg_file = getattr(pkg, "__file__", None)
        if pkg_file is None:
            continue
        candidate = Path(pkg_file).resolve().parent / "statuses.json"
        if candidate.is_file():
            return candidate
    return None


def _member_name(code: str) -> str:
    name = code.upper()
    if not name.isidentifier():
        raise SystemExit(f"status code {code!r} is not a valid enum member")
    return name


def render(statuses_doc: dict) -> str:
    lines = [
        "# GENERATED from porto_features/statuses.json — do not edit.\n",
        "# Run: make sync-bindings\n",
        "\n",
        "from enum import Enum\n",
        "\n",
        "\n",
        "class PortoStatus(str, Enum):\n",
        '    """Normalized carrier status. Not mark existence, and not an unknown bucket."""\n',
        "\n",
    ]
    for row in statuses_doc.get("codes") or []:
        code = str(row["code"])
        lines.append(f'    {_member_name(code)} = "{code}"\n')
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if committed statuses.py does not match the catalog render.",
    )
    args = parser.parse_args()

    sdk_root = Path(__file__).resolve().parents[2]
    output_path = sdk_root / "porto_sdk" / "statuses.py"
    statuses_path = _resolve_statuses_json()
    if statuses_path is None:
        print(
            "statuses.json not in installed porto-features yet; skipping status binding check",
            file=sys.stderr,
        )
        return 0

    rendered = render(json.loads(statuses_path.read_text(encoding="utf-8")))
    if args.check:
        existing = output_path.read_text(encoding="utf-8") if output_path.is_file() else ""
        if existing != rendered:
            print(
                "Python status bindings out of date — run: make sync-bindings",
                file=sys.stderr,
            )
            return 1
        print(f"OK {output_path.relative_to(sdk_root)} matches {statuses_path}")
        return 0

    output_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote {output_path.relative_to(sdk_root)} from {statuses_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
