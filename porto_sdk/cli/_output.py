"""
CLI output formatting. Single responsibility: format and print CLI output.
Styled layout with gruncellka branding when not --json. Same style as TypeScript SDK.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from typing import Any

from ..services.porto_resolver import Porto
from ._constants import BRANDING


def serialize_porto(porto: Porto) -> dict[str, Any]:
    """Canonical JSON representation of a resolved Porto (matches SDK public shape)."""
    return porto.model_dump(mode="json")


def porto_human_summary(porto: Porto) -> dict[str, Any]:
    """Presentation projection for styled resolve output — not the public Porto contract."""
    summary: dict[str, Any] = {
        "product": {"id": porto.product.id, "name": porto.product.name},
        "zone": {"id": porto.zone.id, "name": porto.zone.name},
        "price": {"amount": porto.amount, "currency": porto.currency},
        "tracking": porto.tracking,
        "restrictions": asdict(porto.restrictions),
    }
    if porto.warnings:
        summary["warnings"] = list(porto.warnings)
    return summary


def restrictions_summary(restrictions: dict[str, Any]) -> str | None:
    """One-line human summary for resolve restrictions."""
    impact = restrictions.get("impact")
    legal = restrictions.get("legal") or []
    routing = restrictions.get("routing") or []
    if not impact and not legal and not routing:
        return None
    parts: list[str] = []
    if impact:
        parts.append(f"impact={impact}")
    if legal:
        parts.append(f"{len(legal)} legal")
    if routing:
        parts.append(f"{len(routing)} routing")
    summary = ", ".join(parts)
    if legal or routing:
        summary += " (use restrictions.check for region detail)"
    return summary


def _format_value(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (str, int, float)):
        return str(v)
    if isinstance(v, list):
        return ", ".join(_format_value(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v)
    return str(v)


def _normalize_summary_payload(obj: dict[str, Any]) -> dict[str, Any]:
    """Map flat price() payloads into resolve-style keys for styled output."""
    if "price" in obj or "amount" not in obj:
        return obj
    normalized = dict(obj)
    product_id = normalized.get("product_id") or normalized.get("productId")
    if product_id is not None and "product" not in normalized:
        normalized["product"] = {"id": product_id}
    zone = normalized.get("zone")
    zone_id = normalized.get("zone_id") or normalized.get("zoneId")
    if zone_id is not None and not isinstance(zone, dict):
        normalized["zone"] = {"id": zone_id}
    elif isinstance(zone, str):
        normalized["zone"] = {"id": zone}
    normalized["price"] = {
        "amount": normalized["amount"],
        "currency": normalized.get("currency", "EUR"),
    }
    return normalized


def _format_summary_lines(obj: dict[str, Any]) -> list[str]:
    obj = _normalize_summary_payload(obj)
    product = obj.get("product")
    zone = obj.get("zone")
    price = obj.get("price")
    has_calc_style = product is not None or zone is not None or price is not None

    lines: list[tuple[str, str]] = []
    if has_calc_style:
        if obj.get("provider") is not None:
            lines.append(("provider", str(obj["provider"])))
        if isinstance(product, dict):
            if product.get("name") is not None:
                lines.append(("product", str(product["name"])))
            else:
                lines.append(("product", str(product.get("id", product))))
        elif product is not None:
            lines.append(("product", str(product)))
        if isinstance(zone, dict):
            if zone.get("name") is not None:
                lines.append(("zone", str(zone["name"])))
            else:
                lines.append(("zone", str(zone.get("id", zone))))
        elif zone is not None:
            lines.append(("zone", str(zone)))
        if isinstance(price, dict) and price.get("amount") is not None:
            amount = float(price["amount"])
            curr = price.get("currency", "EUR")
            formatted = f"{amount / 100:.2f}".replace(".", ",") + " " + str(curr)
            lines.append(("price", formatted))
        elif price is not None:
            lines.append(("price", json.dumps(price)))
        tracking = obj.get("tracking")
        if tracking is not None:
            lines.append(("tracking", str(tracking)))
        restrictions = obj.get("restrictions")
        if isinstance(restrictions, dict):
            summary = restrictions_summary(restrictions)
            if summary:
                lines.append(("restrictions", summary))
        warnings = obj.get("warnings")
        if isinstance(warnings, list) and warnings:
            lines.append(("warnings", "; ".join(str(w) for w in warnings)))
    else:
        for k, v in obj.items():
            if v is None:
                lines.append((k, "-"))
            elif isinstance(v, list):
                lines.append((k, ", ".join(str(x) for x in v) if v else "(none)"))
            elif isinstance(v, dict):
                continue
            else:
                lines.append((k, str(v)))

    if lines:
        max_key = max(len(k) for k, _ in lines)
        max_key = max(max_key, 8)
        return [f"  {k:<{max_key}}  {v}" for k, v in lines]
    return []


def _print_pretty(obj: dict[str, Any], indent: str = "") -> list[str]:
    out: list[str] = []
    for k, v in obj.items():
        if isinstance(v, dict) and not isinstance(v, type):
            sub = v
            if len(sub) <= 2 and not any(isinstance(x, (dict, list)) for x in sub.values()):
                parts = [f"{a}={_format_value(b)}" for a, b in sub.items()]
                out.append(f"{indent}{k}: {', '.join(parts)}")
            else:
                out.append(f"{indent}{k}:")
                out.extend(_print_pretty(sub, indent + "  "))
        else:
            out.append(f"{indent}{k}: {_format_value(v)}")
    return out


def is_json_mode(args: argparse.Namespace) -> bool:
    """Whether to output machine-readable JSON."""
    return bool(getattr(args, "json", False))


def print_output(payload: Any, args: argparse.Namespace) -> None:
    """Print payload as JSON or styled human-readable based on args."""
    if isinstance(payload, Porto):
        payload = serialize_porto(payload) if is_json_mode(args) else porto_human_summary(payload)

    if is_json_mode(args):
        print(json.dumps(payload, indent=2, default=str, ensure_ascii=False))
        return

    cmd = getattr(args, "_command", "porto")
    header = f"Porto SDK {cmd} {BRANDING}"

    if isinstance(payload, dict):
        summary = _format_summary_lines(payload)
        body_lines = summary if summary else [f"  {s}" for s in _print_pretty(payload)]
    else:
        body_lines = [f"  {payload}"]

    print(header)
    print()
    for line in body_lines:
        print(line)
