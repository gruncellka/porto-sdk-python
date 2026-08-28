"""
CLI runner. Single responsibility: argument parsing and command dispatch.
Thin shell: parse → dispatch. Catches only PortoError.
"""

import argparse
import asyncio
import sys
from importlib.metadata import version

from ..errors import PortoError
from . import _commands
from ._config_store import DEFAULT_PROVIDER
from ._constants import BRANDING
from ._validation import add_output_flags, add_provider_flag


def _get_cli_version() -> str:
    try:
        return version("gruncellka-porto-sdk")
    except Exception:
        return "0.0.0"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="porto",
        description=f"Porto SDK CLI {BRANDING}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=_get_cli_version())
    sub = parser.add_subparsers(dest="command", required=True)

    # identify
    identify = sub.add_parser(
        "identify", help="Identify envelope and candidate products from format/dimensions + weight"
    )
    identify.add_argument("--weight", type=int)
    identify.add_argument("--format")
    identify.add_argument("--length", type=float)
    identify.add_argument("--width", type=float)
    identify.add_argument("--height", type=float)
    identify.add_argument("--thickness", type=float)
    add_provider_flag(identify)
    add_output_flags(identify)
    identify.set_defaults(func=_commands.cmd_identify)

    # resolve
    resolve = sub.add_parser("resolve", help="Resolve Porto for destination + weight")
    resolve.add_argument("--country")
    resolve.add_argument("--weight", type=int)
    resolve.add_argument("--envelope")
    resolve.add_argument("--product")
    resolve.add_argument("--region")
    add_provider_flag(resolve)
    add_output_flags(resolve)
    resolve.set_defaults(func=_commands.cmd_resolve)

    # price
    price = sub.add_parser("price", help="Price a letter for destination + weight")
    price.add_argument("--country")
    price.add_argument("--weight", type=int)
    price.add_argument("--envelope")
    price.add_argument("--product")
    add_provider_flag(price)
    add_output_flags(price)
    price.set_defaults(func=_commands.cmd_price)

    mark_cmd = sub.add_parser("mark", help="Create a PortoMark using the selected provider")
    mark_cmd.add_argument("--country")
    mark_cmd.add_argument("--weight", type=int)
    mark_cmd.add_argument("--envelope")
    mark_cmd.add_argument("--product")
    mark_cmd.add_argument("--value", type=int)
    mark_cmd.add_argument("--idempotency-key")
    add_provider_flag(mark_cmd)
    add_output_flags(mark_cmd)
    mark_cmd.set_defaults(func=_commands.cmd_mark)

    # track
    track = sub.add_parser("track", help="Track shipment status")
    track.add_argument("--tracking-number")
    add_provider_flag(track)
    add_output_flags(track)
    track.set_defaults(func=_commands.cmd_track)

    # auth
    auth = sub.add_parser("auth", help="Authentication and credential commands")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)

    auth_login = auth_sub.add_parser("login", help="Store provider credentials in local config")
    auth_login.add_argument("--username")
    auth_login.add_argument("--password")
    auth_login.add_argument(
        "--provider",
        help=f"Provider to store credentials for (default from config or {DEFAULT_PROVIDER})",
    )
    auth_login.add_argument("--wire", help="Wire id (default per provider)")
    auth_login.add_argument("--base-url", help="Provider API base URL")
    auth_login.add_argument("--dhl-api-key")
    auth_login.add_argument("--dhl-api-secret")
    auth_login.add_argument("--partner-id", help="Wire credential: partner_id")
    auth_login.add_argument("--customer-id", help="Wire credential: customer_id")
    auth_login.add_argument("--application-id", help="Wire credential: application_id")
    add_output_flags(auth_login)
    auth_login.set_defaults(func=_commands.cmd_auth)

    auth_status = auth_sub.add_parser(
        "status", help="Show authentication status for current provider"
    )
    add_provider_flag(auth_status)
    add_output_flags(auth_status)
    auth_status.set_defaults(func=_commands.cmd_auth_status)

    auth_logout = auth_sub.add_parser("logout", help="Remove stored credentials for provider")
    auth_logout.add_argument("--provider", help="Provider to logout from (default: current)")
    add_output_flags(auth_logout)
    auth_logout.set_defaults(func=_commands.cmd_auth_logout)

    # config
    config = sub.add_parser("config", help="Runtime configuration commands")
    config_sub = config.add_subparsers(dest="config_command", required=True)

    config_check = config_sub.add_parser(
        "check", help="Validate and print current SDK configuration"
    )
    add_provider_flag(config_check)
    add_output_flags(config_check)
    config_check.set_defaults(func=_commands.cmd_validate_config)

    config_init = config_sub.add_parser("init", help="Create a local CLI config file")
    config_init.add_argument("--force", action="store_true")
    add_output_flags(config_init)
    config_init.set_defaults(func=_commands.cmd_config_init)

    args = parser.parse_args()

    # Derive command name for styled output (same as TypeScript)
    if hasattr(args, "auth_command") and args.auth_command:
        args._command = f"auth {args.auth_command}"
    elif hasattr(args, "config_command") and args.config_command:
        args._command = f"config {args.config_command}"
    else:
        args._command = getattr(args, "command", "porto")

    try:
        if asyncio.iscoroutinefunction(args.func):
            asyncio.run(args.func(args))
        else:
            args.func(args)
    except PortoError as error:
        print(error.args[0] if error.args else str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception as error:
        print(f"Fatal error: {error}", file=sys.stderr)
        raise SystemExit(1)
