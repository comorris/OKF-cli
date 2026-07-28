from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .bundles import init_bundle
from .catalog import init_catalog, list_bundles, register_bundle
from .config import config_report, resolve_catalog
from .errors import ConfigurationError, OkfError, OperationalError
from .filesystem import FileSystem
from .operations import OperationResult
from .output import CommandResult, render_error, render_result
from .paths import discover_bundle


def _add_format_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        dest="output_format",
        default=argparse.SUPPRESS,
        help="render results as text or JSON",
    )


def _add_catalog_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--catalog", type=Path, help="catalog root")


def _add_bundle_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--bundle", type=Path, help="bundle root (defaults to project discovery)")


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
    parser.add_argument("--version", action="version", version=f"okf-cli {__version__}")

    commands = parser.add_subparsers(dest="command", required=True)

    config = commands.add_parser("config", help="inspect configuration")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_show = config_commands.add_parser("show", help="show resolved configuration")
    _add_format_option(config_show)
    _add_catalog_option(config_show)

    catalog = commands.add_parser("catalog", help="manage the global catalog")
    catalog_commands = catalog.add_subparsers(dest="catalog_command", required=True)
    catalog_init = catalog_commands.add_parser("init", help="initialize a catalog")
    _add_format_option(catalog_init)
    _add_catalog_option(catalog_init)
    catalog_init.add_argument("--title", required=True)
    catalog_init.add_argument("--description", required=True)
    catalog_init.add_argument("--generated-by", default="okf-cli/0.1.0")
    catalog_init.add_argument("--dry-run", action="store_true")

    bundle = commands.add_parser("bundle", help="manage project bundles")
    bundle_commands = bundle.add_subparsers(dest="bundle_command", required=True)

    bundle_init = bundle_commands.add_parser("init", help="initialize a project bundle")
    _add_format_option(bundle_init)
    _add_bundle_option(bundle_init)
    _add_catalog_option(bundle_init)
    bundle_init.add_argument("--title", required=True)
    bundle_init.add_argument("--description", required=True)
    bundle_init.add_argument("--generated-by", default="okf-cli/0.1.0")
    bundle_init.add_argument("--no-gitignore", action="store_true")
    bundle_init.add_argument("--no-register", "--no-registration", dest="no_register", action="store_true")
    bundle_init.add_argument("--no-index", dest="no_index", action="store_true")
    bundle_init.add_argument("--no-log", dest="no_log", action="store_true")
    bundle_init.add_argument("--dry-run", action="store_true")

    bundle_register = bundle_commands.add_parser("register", help="register an existing bundle")
    _add_format_option(bundle_register)
    _add_bundle_option(bundle_register)
    _add_catalog_option(bundle_register)
    bundle_register.add_argument("--generated-by", default="okf-cli/0.1.0")
    bundle_register.add_argument("--dry-run", action="store_true")

    bundle_list = bundle_commands.add_parser("list", help="list registered bundles")
    _add_format_option(bundle_list)
    _add_catalog_option(bundle_list)

    return parser


def command_name(args: argparse.Namespace) -> str:
    names = [getattr(args, "command", None)]
    for attribute in (
        "config_command",
        "catalog_command",
        "bundle_command",
        "concept_command",
        "index_command",
        "log_command",
    ):
        value = getattr(args, attribute, None)
        if value:
            names.append(value)
    return ".".join(value for value in names if value)


def _catalog_path(explicit: Path | None, *, required: bool = False) -> Path | None:
    resolved = resolve_catalog(explicit, os.environ, Path.home()).path
    if required and resolved is None:
        raise ConfigurationError("catalog path is required; pass --catalog or configure OKF_CATALOG_ROOT")
    return resolved


def _operation_data(result: OperationResult) -> dict[str, object]:
    data = dict(result.data)
    if result.changes:
        data["changes"] = [
            {
                "operation": change.operation,
                "path": str(change.path),
            }
            for change in result.changes
        ]
    return data


def dispatch_command(args: argparse.Namespace) -> CommandResult:
    command = command_name(args)
    try:
        if command == "config.show":
            return CommandResult(
                command=command,
                data=config_report(getattr(args, "catalog", None), os.environ, Path.home()),
            )

        if command == "catalog.init":
            catalog_path = _catalog_path(getattr(args, "catalog", None), required=True)
            result = init_catalog(
                catalog_path,
                title=args.title,
                description=args.description,
                generated_by=args.generated_by,
                fs=FileSystem(dry_run=args.dry_run),
            )
            return CommandResult(command=command, data=_operation_data(result))

        if command == "bundle.init":
            bundle_path = getattr(args, "bundle", None) or discover_bundle(Path.cwd())
            result = init_bundle(
                bundle_path,
                title=args.title,
                description=args.description,
                catalog=_catalog_path(getattr(args, "catalog", None)),
                register=not args.no_register,
                update_gitignore=not args.no_gitignore,
                rebuild=not args.no_index,
                log_change=not args.no_log,
                generated_by=args.generated_by,
                fs=FileSystem(dry_run=args.dry_run),
            )
            return CommandResult(command=command, data=_operation_data(result))

        if command == "bundle.register":
            bundle_path = getattr(args, "bundle", None) or discover_bundle(Path.cwd())
            catalog_path = _catalog_path(getattr(args, "catalog", None), required=True)
            result = register_bundle(
                catalog_path,
                bundle_path,
                generated_by=args.generated_by,
                fs=FileSystem(dry_run=args.dry_run),
            )
            return CommandResult(command=command, data=_operation_data(result))

        if command == "bundle.list":
            catalog_path = _catalog_path(getattr(args, "catalog", None), required=True)
            return CommandResult(command=command, data={"bundles": list_bundles(catalog_path)})
    except OkfError:
        raise
    except (OSError, ValueError) as exc:
        raise ConfigurationError(str(exc)) from exc

    raise OperationalError(f"unsupported command: {command}")


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
    return 0


def entrypoint() -> None:
    raise SystemExit(main())
