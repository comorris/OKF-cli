from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .catalog import DEFAULT_ACTOR, register_bundle
from .documents import ConceptDocument, DocumentError, parse_concept, render_concept
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


def _git_root(path: Path) -> Path | None:
    current = path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _update_gitignore(bundle_root: Path, fs: FileSystem) -> None:
    git_root = _git_root(bundle_root)
    if git_root is None:
        return
    ignore_path = git_root / ".gitignore"
    existing = fs.read_text(ignore_path) if fs.is_file(ignore_path) else ""
    if any(line.strip() == "/okf/" for line in existing.splitlines()):
        return
    if existing and not existing.endswith("\n"):
        existing += "\n"
    write_if_changed(fs, ignore_path, f"{existing}/okf/\n")


def init_bundle(
    bundle_root: Path,
    *,
    title: str,
    description: str,
    catalog: Path | None,
    register: bool = True,
    update_gitignore: bool = True,
    rebuild: bool = True,
    log_change: bool = True,
    generated_by: str = DEFAULT_ACTOR,
    now: datetime | None = None,
    fs: FileSystem,
) -> OperationResult:
    bundle_root = Path(bundle_root)
    if not title.strip() or not description.strip():
        raise ConfigurationError("bundle title and description are required")
    if fs.exists(bundle_root) and not fs.is_dir(bundle_root):
        raise ConfigurationError(f"bundle path is not a directory: {bundle_root}")
    if not fs.is_dir(bundle_root):
        fs.mkdir(bundle_root)

    bundle_path = bundle_root / "bundle.md"
    metadata = {
        "type": "Knowledge Bundle",
        "title": title,
        "description": description,
        "status": "stable",
        "generated": {"by": generated_by, "at": _timestamp(now)},
    }
    if fs.is_file(bundle_path):
        try:
            existing = parse_concept(fs.read_text(bundle_path))
        except DocumentError as exc:
            raise ConfigurationError(f"invalid existing bundle metadata: {exc}") from exc
        for key in ("type", "title", "description"):
            if existing.metadata.get(key) != metadata[key]:
                raise ConflictError(f"existing metadata conflicts at {bundle_path}")
    else:
        write_if_changed(fs, bundle_path, render_concept(ConceptDocument(metadata, "")))

    if log_change and not fs.is_file(bundle_root / "log.md"):
        append_log(
            bundle_root,
            "Initialization",
            "Created the bundle.",
            date=(now or datetime.now(timezone.utc)).date(),
            fs=fs,
        )
    if rebuild:
        rebuild_indexes(bundle_root, fs)
    if update_gitignore:
        _update_gitignore(bundle_root, fs)

    registered = False
    if register and catalog is not None:
        result = register_bundle(
            Path(catalog),
            bundle_root,
            generated_by=generated_by,
            now=now,
            fs=fs,
        )
        registered = bool(result.data.get("registered", False))
    return OperationResult(
        data={"path": str(bundle_root), "registered": registered},
        changes=fs.changes,
    )
