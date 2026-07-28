from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .config import config_report
from .errors import OkfError, OperationalError
from .output import CommandResult, render_error, render_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="okf",
        description="Manage portable OKF knowledge bundles.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        dest="output_format",
        help="render results as text or JSON",
    )
    parser.add_argument("--catalog", dest="catalog", type=Path, help="catalog root")
    parser.add_argument("--version", action="version", version=f"okf-cli {__version__}")

    commands = parser.add_subparsers(dest="command", required=True)
    config = commands.add_parser("config", help="inspect configuration")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("show", help="show resolved configuration")
    return parser


def command_name(args: argparse.Namespace) -> str:
    names = [getattr(args, "command", None)]
    for attribute in ("config_command", "catalog_command", "bundle_command"):
        value = getattr(args, attribute, None)
        if value:
            names.append(value)
    return ".".join(value for value in names if value)


def dispatch_command(args: argparse.Namespace) -> CommandResult:
    if args.command == "config" and args.config_command == "show":
        return CommandResult(
            command="config.show",
            data=config_report(args.catalog, os.environ, Path.home()),
        )
    raise OperationalError(f"unsupported command: {command_name(args)}")


def _format_name(args: argparse.Namespace) -> str:
    return getattr(args, "output_format", "text")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    format_name = _format_name(args)
    command = command_name(args)
    try:
        result = dispatch_command(args)
    except OkfError as exc:
        sys.stderr.write(render_error(command, exc, format_name))
        return int(exc.exit_code)
    except Exception:
        error = OperationalError("unexpected error")
        sys.stderr.write(render_error(command, error, format_name))
        return int(error.exit_code)

    sys.stdout.write(render_result(result, format_name))
    return int(0)


def entrypoint() -> None:
    raise SystemExit(main())
