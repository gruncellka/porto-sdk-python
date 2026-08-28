#!/usr/bin/env python3
"""Generate porto_sdk/errors/codes.py from porto-features errors.json.

Sole SoT for public PORTO_* string values: porto_features/errors.json codes[].

Usage:
  python scripts/build/build_error_bindings.py          # write
  python scripts/build/build_error_bindings.py --check   # fail on drift
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _resolve_errors_json() -> Path:
    env_path = os.environ.get("PORTO_FEATURES_PATH")
    if env_path:
        root = Path(env_path).expanduser().resolve()
        for candidate in (root / "errors.json", root / "porto_features" / "errors.json"):
            if candidate.is_file():
                return candidate
        raise SystemExit(
            f"PORTO_FEATURES_PATH={env_path} is set but errors.json was not found "
            f"(expected under the features package root)."
        )

    for module_name in ("gruncellka_porto_features", "porto_features"):
        try:
            pkg = __import__(module_name)
        except ImportError:
            continue
        pkg_file = getattr(pkg, "__file__", None)
        if pkg_file is None:
            continue
        root = Path(pkg_file).resolve().parent
        candidate = root / "errors.json"
        if candidate.is_file():
            return candidate

    raise SystemExit(
        "porto-features errors.json not found. Install gruncellka-porto-features "
        "or set PORTO_FEATURES_PATH."
    )


def _render_member(code: str, domain: str, description: str) -> str:
    comment = f"{domain}: {description}"
    # Keep short one-liners compact; wrap long comments like the existing file.
    if len(code) + len(comment) < 72:
        return f'    {code} = "{code}"  # {comment}\n'
    return (
        f"    {code} = (\n"
        f'        "{code}"  # {comment}\n'
        f"    )\n"
    )


def render(errors_doc: dict) -> str:
    lines = [
        "# GENERATED from porto_features/errors.json — do not edit.\n",
        "# Run: make sync-error-bindings\n",
        "\n",
        "from enum import Enum\n",
        "\n",
        "\n",
        "class PortoErrorCode(str, Enum):\n",
    ]
    for row in errors_doc.get("codes") or []:
        code = str(row["code"])
        domain = str(row.get("domain") or "unknown")
        description = str(row.get("description") or "")
        lines.append(_render_member(code, domain, description))
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if committed codes.py does not match the catalog render.",
    )
    args = parser.parse_args()

    sdk_root = Path(__file__).resolve().parents[2]
    output_path = sdk_root / "porto_sdk" / "errors" / "codes.py"
    errors_path = _resolve_errors_json()
    errors_doc = json.loads(errors_path.read_text(encoding="utf-8"))
    rendered = render(errors_doc)

    if args.check:
        existing = output_path.read_text(encoding="utf-8") if output_path.is_file() else ""
        if existing != rendered:
            print(
                "Python error bindings out of date — run: make sync-error-bindings",
                file=sys.stderr,
            )
            return 1
        print(f"OK {output_path.relative_to(sdk_root)} matches {errors_path}")
        return 0

    output_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote {output_path.relative_to(sdk_root)} from {errors_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
