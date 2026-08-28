"""
CLI command handlers. Single responsibility: orchestrate client calls and output.
"""

from __future__ import annotations

import argparse

from ..execution import PortoMarkRequest
from ._bootstrap import bootstrap, bound_cli_provider, build_cli_client, resolve_provider
from ._config_store import (
    clear_provider_wire,
    config_exists,
    get_config_check_summary,
    get_config_path,
    get_provider_wire,
    init_config,
    save_provider_wire,
)
from ._output import print_output
from ._validation import ensure_required_flags
from .integrations.registry import (
    build_login_output_summary,
    build_wire_payload,
    get_wire_status_summary,
)


async def cmd_identify(args: argparse.Namespace) -> None:
    ensure_required_flags(args, "identify", [("weight", "--weight")])
    if not getattr(args, "format", None) and not any(
        getattr(args, dim, None) is not None for dim in ("length", "width", "height")
    ):
        raise SystemExit("identify requires --format and/or dimensions")
    client = build_cli_client(args)
    dimensions = None
    if any(
        getattr(args, dim, None) is not None for dim in ("length", "width", "height", "thickness")
    ):
        dimensions = {
            "length": getattr(args, "length", None),
            "width": getattr(args, "width", None),
            "height": getattr(args, "height", None),
            "thickness": getattr(args, "thickness", None),
        }
    result = await client.envelopes.identify(
        envelope_format=getattr(args, "format", None),
        dimensions=dimensions,
        weight=int(args.weight),
    )
    print_output(
        {
            "dimensions": result.dimensions,
            "format": result.format,
            "resolution_weight": result.resolution_weight,
        },
        args,
    )


def cmd_resolve(args: argparse.Namespace) -> None:
    ensure_required_flags(
        args,
        "resolve",
        [("country", "--country"), ("weight", "--weight")],
    )
    bound = bound_cli_provider(args)
    result = bound.resolve(
        country_code=str(args.country),
        weight=int(args.weight),
        envelope_id=str(args.envelope) if getattr(args, "envelope", None) else None,
        product_id=str(args.product) if getattr(args, "product", None) else None,
    )
    print_output(result, args)


def cmd_price(args: argparse.Namespace) -> None:
    ensure_required_flags(
        args,
        "price",
        [("country", "--country"), ("weight", "--weight")],
    )
    bound = bound_cli_provider(args)
    pricing = bound.price(
        country_code=str(args.country),
        weight=int(args.weight),
        envelope_id=str(args.envelope) if getattr(args, "envelope", None) else None,
        product_id=str(args.product) if getattr(args, "product", None) else None,
    )
    print_output(
        {
            "product_id": pricing.product_id,
            "zone": pricing.zone_id,
            "weight": pricing.weight,
            "amount": pricing.amount,
            "currency": pricing.currency,
        },
        args,
    )


async def cmd_mark(args: argparse.Namespace) -> None:
    ensure_required_flags(
        args,
        "mark",
        [
            ("country", "--country"),
            ("weight", "--weight"),
        ],
    )
    bound = bound_cli_provider(args)
    porto = bound.resolve(
        country_code=str(args.country),
        weight=int(args.weight),
        envelope_id=str(args.envelope) if getattr(args, "envelope", None) else None,
        product_id=str(args.product) if getattr(args, "product", None) else None,
    )
    mark_result = await bound.mark(
        PortoMarkRequest(
            porto=porto,
            idempotency=args.idempotency_key,
        )
    )
    mark = mark_result[0] if isinstance(mark_result, list) else mark_result
    print_output(
        {
            "id": mark.id,
            "external_id": mark.external_id,
            "amount": mark.amount,
            "currency": mark.currency,
            "idempotency_key": args.idempotency_key,
        },
        args,
    )


async def cmd_track(args: argparse.Namespace) -> None:
    ensure_required_flags(args, "track", [("tracking_number", "--tracking-number")])
    bound = bound_cli_provider(args)
    status = await bound.track.get(args.tracking_number)
    print_output(status, args)


def cmd_auth(args: argparse.Namespace) -> None:
    ensure_required_flags(
        args, "auth login", [("username", "--username"), ("password", "--password")]
    )
    boot = bootstrap(args)
    payload = build_wire_payload(args, boot.provider, boot.wire)
    save_provider_wire(boot.provider, boot.wire, payload)
    out = build_login_output_summary(args, boot.provider, boot.wire, str(get_config_path()))
    print_output(out, args)


def cmd_auth_status(args: argparse.Namespace) -> None:
    boot = bootstrap(args)
    wire_config = get_provider_wire(boot.provider, boot.wire)
    summary = get_wire_status_summary(wire_config, boot.provider, boot.wire)
    print_output(summary, args)


def cmd_auth_logout(args: argparse.Namespace) -> None:
    boot = bootstrap(args)
    if not config_exists():
        print_output(
            {"logged_out": False, "provider": boot.provider, "reason": "No config file found"},
            args,
        )
        return
    cleared = clear_provider_wire(boot.provider, boot.wire)
    print_output(
        {
            "logged_out": cleared,
            "provider": boot.provider,
            "config_path": str(get_config_path()),
        },
        args,
    )


def cmd_validate_config(args: argparse.Namespace) -> None:
    summary = get_config_check_summary(provider_override=resolve_provider(args))
    print_output(summary, args)


def cmd_config_init(args: argparse.Namespace) -> None:
    force = bool(getattr(args, "force", False))
    result = init_config(force=force)
    print_output(result, args)
