from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

from . import __version__
from .bundles import init_bundle
from .catalog import init_catalog, list_bundles, register_bundle
from .concepts import create_concept
from .config import config_report, resolve_catalog
from .errors import ConfigurationError, OkfError, OperationalError
from .filesystem import FileSystem
from .indexes import rebuild_indexes
from .logs import add_log
from .operations import OperationResult
from .output import CommandResult, render_error, render_result, render_validation_error
from .paths import discover_bundle
from .validation import ValidationFailure, finding_dict, validate_bundle


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

    concept = commands.add_parser("concept", help="manage concepts")
    concept_commands = concept.add_subparsers(dest="concept_command", required=True)
    concept_create = concept_commands.add_parser("create", help="create a concept")
    _add_format_option(concept_create)
    _add_bundle_option(concept_create)
    concept_create.add_argument("concept_id")
    concept_create.add_argument("--type", dest="concept_type", required=True)
    concept_create.add_argument("--title")
    concept_create.add_argument("--description")
    concept_create.add_argument("--tag", dest="tags", action="append", default=[])
    concept_create.add_argument("--status", choices=("draft", "stable", "deprecated"))
    concept_create.add_argument("--generated-by", default="okf-cli/0.1.0")
    concept_create.add_argument("--force", action="store_true")
    concept_create.add_argument("--no-index", dest="no_index", action="store_true")
    concept_create.add_argument("--no-log", dest="no_log", action="store_true")
    body = concept_create.add_mutually_exclusive_group()
    body.add_argument("--body")
    body.add_argument("--body-file", type=Path)
    concept_create.add_argument("--dry-run", action="store_true")

    index = commands.add_parser("index", help="manage indexes")
    index_commands = index.add_subparsers(dest="index_command", required=True)
    index_rebuild = index_commands.add_parser("rebuild", help="rebuild all indexes")
    _add_format_option(index_rebuild)
    _add_bundle_option(index_rebuild)
    index_rebuild.add_argument("--catalog-mode", action="store_true")
    index_rebuild.add_argument("--dry-run", action="store_true")

    log = commands.add_parser("log", help="manage update logs")
    log_commands = log.add_subparsers(dest="log_command", required=True)
    log_add = log_commands.add_parser("add", help="append a log entry")
    _add_format_option(log_add)
    _add_bundle_option(log_add)
    log_add.add_argument("--scope", default="", help="bundle-relative directory scope")
    log_add.add_argument("--kind", choices=("Initialization", "Creation", "Update", "Deprecation"), required=True)
    log_add.add_argument("--message", required=True)
    log_add.add_argument("--date")
    log_add.add_argument("--dry-run", action="store_true")

    validate = commands.add_parser("validate", help="validate a bundle")
    _add_format_option(validate)
    _add_bundle_option(validate)

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


def _body_from_args(args: argparse.Namespace) -> str:
    if args.body_file is None:
        return args.body or ""
    try:
        return args.body_file.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigurationError(f"could not read UTF-8 body file {args.body_file}: {exc}") from exc


def _date_from_arg(value: str | None) -> date:
    if value is None:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigurationError("--date must use YYYY-MM-DD") from exc


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

        if command == "concept.create":
            bundle_path = getattr(args, "bundle", None) or discover_bundle(Path.cwd())
            result = create_concept(
                bundle_path,
                args.concept_id,
                concept_type=args.concept_type,
                title=args.title,
                description=args.description,
                tags=tuple(args.tags),
                status=args.status,
                body=_body_from_args(args),
                generated_by=args.generated_by,
                force=args.force,
                rebuild=not args.no_index,
                log_change=not args.no_log,
                fs=FileSystem(dry_run=args.dry_run),
            )
            return CommandResult(command=command, data=_operation_data(result))

        if command == "index.rebuild":
            bundle_path = getattr(args, "bundle", None) or discover_bundle(Path.cwd())
            if not bundle_path.is_dir():
                raise ConfigurationError(f"bundle does not exist: {bundle_path}")
            fs = FileSystem(dry_run=args.dry_run)
            indexes = rebuild_indexes(bundle_path, fs, catalog=args.catalog_mode)
            data: dict[str, object] = {
                "bundle": str(bundle_path),
                "indexes": [str(path) for path in indexes],
            }
            if fs.changes:
                data["changes"] = [
                    {"operation": change.operation, "path": str(change.path)}
                    for change in fs.changes
                ]
            return CommandResult(command=command, data=data)

        if command == "log.add":
            bundle_path = getattr(args, "bundle", None) or discover_bundle(Path.cwd())
            fs = FileSystem(dry_run=args.dry_run)
            result = add_log(
                bundle_path,
                scope=args.scope,
                kind=args.kind,
                message=args.message,
                date=_date_from_arg(args.date),
                fs=fs,
            )
            return CommandResult(command=command, data=_operation_data(result))

        if command == "validate":
            bundle_path = getattr(args, "bundle", None) or discover_bundle(Path.cwd())
            if not bundle_path.is_dir():
                raise ConfigurationError(f"bundle does not exist: {bundle_path}")
            findings = validate_bundle(bundle_path)
            data = {
                "bundle": str(bundle_path),
                "findings": [finding_dict(finding) for finding in findings],
            }
            errors = [finding for finding in findings if finding.severity == "error"]
            warnings = tuple(finding.message for finding in findings if finding.severity == "warning")
            if errors:
                raise ValidationFailure(findings)
            return CommandResult(command=command, data=data, warnings=warnings)
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
    except ValidationFailure as exc:
        rendered = render_validation_error(command, exc.findings, format_name)
        if format_name == "json":
            sys.stdout.write(rendered)
        else:
            sys.stderr.write(rendered)
        return int(exc.exit_code)
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
