#!/usr/bin/env python3
"""Fail closed unless paid Internetmarke canary env is complete."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from porto_sdk.adapters.deutschepost.internetmarke.bootstrap import (  # noqa: E402
    load_internetmarke_config,
)


def main() -> int:
    if os.environ.get("I_ACCEPT_PAID_API_COST") != "1":
        print("adapter-canary: I_ACCEPT_PAID_API_COST=1 is required", file=sys.stderr)
        return 1
    im = load_internetmarke_config("deutschepost", dict(os.environ))
    if im is None:
        print(
            "adapter-canary: missing Internetmarke/DHL API credentials "
            "(PORTO_DEUTSCHEPOST_INTERNETMARKE_API_KEY/SECRET or DHL_API_KEY/SECRET)",
            file=sys.stderr,
        )
        return 1
    creds = im.credentials or {}
    if not creds.get("username") or not creds.get("password"):
        print(
            "adapter-canary: missing Portokasse username/password "
            "(PORTO_DEUTSCHEPOST_INTERNETMARKE_USERNAME/PASSWORD)",
            file=sys.stderr,
        )
        return 1
    print("adapter-canary: Internetmarke env OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
