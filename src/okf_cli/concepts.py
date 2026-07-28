from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .documents import ConceptDocument, DocumentError, parse_concept, render_concept
from .errors import ConfigurationError, ConflictError
from .filesystem import FileSystem
from .indexes import rebuild_indexes
from .logs import append_log
from .operations import OperationResult, write_if_changed
from .paths import resolve_concept_path

_RESERVED_IDS = {"index", "log", "bundle"}
_VALID_STATUS = {"draft", "stable", "deprecated"}


def _timestamp(now: datetime | None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_actor(actor: str) -> None:
    if not isinstance(actor, str) or not actor.strip():
        raise ConfigurationError("generated actor must be non-empty")
    if not ("/" in actor or actor.startswith("human:") or actor.startswith("process:")):
        raise ConfigurationError("generated actor must use the producer/version or human:/process: convention")


def _concept_metadata(
    *,
    concept_type: str,
    title: str | None,
    description: str | None,
    tags: Sequence[str],
    status: str | None,
    generated_by: str,
    generated_at: str,
) -> dict[str, Any]:
    if not isinstance(concept_type, str) or not concept_type.strip():
        raise ConfigurationError("concept type must be non-empty")
    if title is not None and not isinstance(title, str):
        raise ConfigurationError("concept title must be a string")
    if description is not None and not isinstance(description, str):
        raise ConfigurationError("concept description must be a string")
    if isinstance(tags, str):
        raise ConfigurationError("tags must be a sequence of strings")
    tag_values = list(tags)
    if any(not isinstance(tag, str) or not tag.strip() for tag in tag_values):
        raise ConfigurationError("tags must contain non-empty strings")
    if status is not None and status not in _VALID_STATUS:
        raise ConfigurationError(f"invalid status: {status}")
    _validate_actor(generated_by)

    metadata: dict[str, Any] = {"type": concept_type}
    if title is not None:
        metadata["title"] = title
    if description is not None:
        metadata["description"] = description
    if tag_values:
        metadata["tags"] = tag_values
    if status is not None:
        metadata["status"] = status
    metadata["generated"] = {"by": generated_by, "at": generated_at}
    return metadata


def create_concept(
    bundle_root: Path,
    concept_id: str,
    *,
    concept_type: str,
    title: str | None,
    description: str | None,
    tags: Sequence[str],
    status: str | None,
    body: str,
    generated_by: str,
    force: bool,
    rebuild: bool,
    log_change: bool,
    fs: FileSystem,
    now: datetime | None = None,
) -> OperationResult:
    bundle_root = Path(bundle_root)
    if not fs.is_dir(bundle_root):
        raise ConfigurationError(f"bundle does not exist: {bundle_root}")
    if not isinstance(concept_id, str) or not concept_id.strip():
        raise ConfigurationError("concept ID must be non-empty")
    final_segment = Path(concept_id).name
    if final_segment in _RESERVED_IDS:
        raise ConfigurationError(f"reserved concept ID: {concept_id}")
    target = resolve_concept_path(bundle_root, concept_id)
    existed = fs.exists(target)
    if existed and not force:
        raise ConflictError(f"concept already exists: {target}")
    if existed and not fs.is_file(target):
        raise ConfigurationError(f"concept path is not a file: {target}")
    if not isinstance(body, str):
        raise ConfigurationError("concept body must be text")

    metadata = _concept_metadata(
        concept_type=concept_type,
        title=title,
        description=description,
        tags=tags,
        status=status,
        generated_by=generated_by,
        generated_at=_timestamp(now),
    )
    write_if_changed(fs, target, render_concept(ConceptDocument(metadata, body)))

    if rebuild:
        rebuild_indexes(bundle_root, fs)
    if log_change:
        kind = "Update" if existed else "Creation"
        message = f"{'Updated' if existed else 'Created'} {concept_id}."
        append_log(
            bundle_root,
            kind,
            message,
            date=(now or datetime.now(timezone.utc)).date(),
            fs=fs,
        )
    return OperationResult(
        data={"path": str(target), "created": not existed},
        changes=fs.changes,
    )
