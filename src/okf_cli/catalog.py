from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import DEFAULT_ACTOR
from .documents import DocumentError, parse_concept, render_concept, ConceptDocument
from .errors import ConfigurationError, ConflictError
from .filesystem import FileSystem
from .indexes import rebuild_indexes
from .logs import append_log
from .operations import OperationResult, write_if_changed



def _timestamp(now: datetime | None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _metadata(
    *,
    concept_type: str,
    title: str,
    description: str,
    generated_by: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "type": concept_type,
        "title": title,
        "description": description,
        "status": "stable",
        "generated": {"by": generated_by, "at": generated_at},
    }


def _ensure_dir(fs: FileSystem, path: Path) -> None:
    if not fs.is_dir(path):
        fs.mkdir(path)


def _write_document_if_missing(
    fs: FileSystem,
    path: Path,
    metadata: dict[str, Any],
) -> None:
    if fs.is_file(path):
        try:
            existing = parse_concept(fs.read_text(path))
        except DocumentError as exc:
            raise ConfigurationError(f"invalid existing document {path}: {exc}") from exc
        for key in ("type", "title", "description"):
            if existing.metadata.get(key) != metadata[key]:
                raise ConflictError(f"existing metadata conflicts at {path}")
        return
    write_if_changed(fs, path, render_concept(ConceptDocument(metadata, "")))


def init_catalog(
    catalog_root: Path,
    *,
    title: str,
    description: str,
    generated_by: str = DEFAULT_ACTOR,
    now: datetime | None = None,
    fs: FileSystem,
) -> OperationResult:
    catalog_root = Path(catalog_root)
    if not title.strip() or not description.strip():
        raise ConfigurationError("catalog title and description are required")
    _ensure_dir(fs, catalog_root)
    _ensure_dir(fs, catalog_root / "bundles")
    generated_at = _timestamp(now)
    metadata = _metadata(
        concept_type="Knowledge Bundle",
        title=title,
        description=description,
        generated_by=generated_by,
        generated_at=generated_at,
    )
    _write_document_if_missing(fs, catalog_root / "bundle.md", metadata)
    if not fs.is_file(catalog_root / "log.md"):
        append_log(
            catalog_root,
            "Initialization",
            "Created the catalog.",
            date=(now or datetime.now(timezone.utc)).date(),
            fs=fs,
        )
    rebuild_indexes(catalog_root, fs, catalog=True)
    return OperationResult(
        data={"path": str(catalog_root), "catalog": True},
        changes=fs.changes,
    )


def _slugify(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "bundle"


def _resolve_resource(reference_path: Path, resource: object) -> Path | None:
    if not isinstance(resource, str) or not resource.strip():
        return None
    if "://" in resource:
        return None
    path = Path(resource)
    if not path.is_absolute():
        path = reference_path.parent / path
    return path.resolve(strict=False)


def _reference_paths(catalog_root: Path, fs: FileSystem) -> list[Path]:
    directory = catalog_root / "bundles"
    if not fs.is_dir(directory):
        return []
    return [
        path
        for path in fs.iterdir(directory)
        if fs.is_file(path) and path.suffix == ".md" and path.name not in {"index.md", "log.md"}
    ]


def _reference_document(path: Path, fs: FileSystem) -> tuple[dict[str, Any], ConceptDocument]:
    try:
        document = parse_concept(fs.read_text(path))
    except (DocumentError, OSError) as exc:
        raise ConfigurationError(f"invalid bundle reference {path}: {exc}") from exc
    if document.metadata.get("type") != "Knowledge Bundle Reference":
        raise ConfigurationError(f"invalid bundle reference type in {path}")
    return document.metadata, document


def _relative_resource(reference_path: Path, bundle_root: Path) -> str:
    return os.path.relpath(bundle_root.resolve(), reference_path.parent.resolve()).replace(os.sep, "/")


def register_bundle(
    catalog_root: Path,
    bundle_root: Path,
    *,
    generated_by: str = DEFAULT_ACTOR,
    now: datetime | None = None,
    fs: FileSystem,
) -> OperationResult:
    catalog_root = Path(catalog_root)
    bundle_root = Path(bundle_root)
    if not fs.is_dir(catalog_root):
        raise ConfigurationError(f"catalog does not exist: {catalog_root}")
    bundle_document_path = bundle_root / "bundle.md"
    if not fs.is_file(bundle_document_path):
        raise ConfigurationError(f"bundle metadata does not exist: {bundle_document_path}")
    try:
        bundle_document = parse_concept(fs.read_text(bundle_document_path))
    except (DocumentError, OSError) as exc:
        raise ConfigurationError(f"invalid bundle metadata: {exc}") from exc
    metadata = bundle_document.metadata
    if metadata.get("type") != "Knowledge Bundle":
        raise ConfigurationError("bundle.md must have type: Knowledge Bundle")
    title = metadata.get("title")
    description = metadata.get("description")
    if not isinstance(title, str) or not title.strip() or not isinstance(description, str) or not description.strip():
        raise ConfigurationError("bundle.md requires non-empty title and description")

    _ensure_dir(fs, catalog_root / "bundles")
    references = _reference_paths(catalog_root, fs)
    for reference_path in references:
        reference_metadata, _ = _reference_document(reference_path, fs)
        target = _resolve_resource(reference_path, reference_metadata.get("resource"))
        if target == bundle_root.resolve():
            if reference_metadata.get("title") != title or reference_metadata.get("description") != description:
                raise ConflictError(f"registered metadata conflicts at {reference_path}")
            return OperationResult(data={"path": str(reference_path), "registered": False}, changes=fs.changes)

    slug = _slugify(title)
    suffix = 1
    while True:
        filename = f"{slug if suffix == 1 else f'{slug}-{suffix}'}.md"
        reference_path = catalog_root / "bundles" / filename
        if not fs.is_file(reference_path):
            break
        suffix += 1

    generated_at = _timestamp(now)
    reference_metadata = _metadata(
        concept_type="Knowledge Bundle Reference",
        title=title,
        description=description,
        generated_by=generated_by,
        generated_at=generated_at,
    )
    reference_metadata["resource"] = _relative_resource(reference_path, bundle_root)
    write_if_changed(fs, reference_path, render_concept(ConceptDocument(reference_metadata, "")))

    log_date = (now or datetime.now(timezone.utc)).date()
    append_log(
        catalog_root,
        "Creation",
        f"Registered {title}.",
        date=log_date,
        fs=fs,
    )
    rebuild_indexes(catalog_root, fs, catalog=True)
    return OperationResult(
        data={"path": str(reference_path), "registered": True},
        changes=fs.changes,
    )


def unregister_bundle(
    catalog_root: Path,
    bundle_root: Path,
    *,
    now: datetime | None = None,
    fs: FileSystem,
) -> OperationResult:
    """Remove catalog references by resolved target path, even if the target is gone.

    Render the complete operation before applying it. This avoids partial deletion
    on invalid input, but does not provide rollback for I/O failures or concurrent
    catalog modifications.
    """
    if not fs.dry_run:
        from copy import deepcopy

        preview_fs = deepcopy(fs)
        preview_fs.dry_run = True
        result = unregister_bundle(catalog_root, bundle_root, now=now, fs=preview_fs)
        for change in result.changes[len(fs.changes):]:
            if change.operation == "delete":
                fs.remove_file(change.path)
            elif change.operation == "write":
                fs.write_text(change.path, change.content)
            else:
                raise AssertionError(f"unexpected unregister operation: {change.operation}")
        return OperationResult(data=result.data, changes=fs.changes)

    catalog_root = Path(catalog_root)
    bundle_root = Path(bundle_root).resolve(strict=False)
    if not fs.is_dir(catalog_root / "bundles") or not fs.is_file(catalog_root / "bundle.md"):
        raise ConfigurationError(f"catalog does not exist: {catalog_root}")

    # Index rebuilding visits every visible directory. Refuse links before
    # traversal, including dangling links that is_file() would silently omit.
    pending = [catalog_root]
    while pending:
        directory = pending.pop()
        if directory.is_symlink():
            raise ConfigurationError(f"symlink catalog path is not supported: {directory}")
        for path in fs.iterdir(directory):
            if path.is_symlink():
                raise ConfigurationError(f"symlink catalog path is not supported: {path}")
            if fs.is_dir(path):
                if path.name in {"index.md", "log.md"}:
                    raise ConfigurationError(f"catalog output path is a directory: {path}")
                if not path.name.startswith("."):
                    pending.append(path)

    matches: list[Path] = []
    # Validate every reference before deleting anything; don't silently skip bad records.
    for reference_path in _reference_paths(catalog_root, fs):
        metadata, _ = _reference_document(reference_path, fs)
        target = _resolve_resource(reference_path, metadata.get("resource"))
        if target is None:
            raise ConfigurationError(f"invalid bundle reference resource in {reference_path}")
        if target == bundle_root:
            matches.append(reference_path)

    for reference_path in sorted(matches):
        fs.remove_file(reference_path)
    if matches:
        append_log(
            catalog_root,
            "Deprecation",
            f"Unregistered bundle at {bundle_root} ({len(matches)} reference(s)).",
            date=(now or datetime.now(timezone.utc)).date(),
            fs=fs,
        )
        rebuild_indexes(catalog_root, fs, catalog=True)
    return OperationResult(
        data={"bundle": str(bundle_root), "unregistered": bool(matches),
              "paths": [str(path) for path in sorted(matches)]},
        changes=fs.changes,
    )


def list_bundles(catalog_root: Path) -> list[dict[str, str]]:
    catalog_root = Path(catalog_root)
    directory = catalog_root / "bundles"
    if not directory.is_dir():
        raise ConfigurationError(f"catalog does not exist: {catalog_root}")
    bundles: list[dict[str, str]] = []
    for reference_path in sorted(directory.glob("*.md"), key=lambda path: (path.name.casefold(), path.name)):
        if reference_path.name in {"index.md", "log.md"}:
            continue
        try:
            document = parse_concept(reference_path.read_text(encoding="utf-8"))
        except (DocumentError, OSError) as exc:
            raise ConfigurationError(f"invalid bundle reference {reference_path}: {exc}") from exc
        if document.metadata.get("type") != "Knowledge Bundle Reference":
            raise ConfigurationError(f"invalid bundle reference type in {reference_path}")
        title = document.metadata.get("title")
        description = document.metadata.get("description")
        resource = _resolve_resource(reference_path, document.metadata.get("resource"))
        if not isinstance(title, str) or not isinstance(description, str) or resource is None:
            raise ConfigurationError(f"invalid bundle reference metadata in {reference_path}")
        bundles.append({"title": title, "description": description, "path": str(resource)})
    return sorted(bundles, key=lambda bundle: bundle["title"].casefold())
