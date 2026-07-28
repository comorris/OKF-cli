from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .documents import ConceptDocument, DocumentError, parse_concept, render_concept
from .errors import ConfigurationError, ConflictError, ValidationError
from .filesystem import FileSystem
from .indexes import rebuild_indexes
from .logs import append_log
from .operations import OperationResult, write_if_changed
from .paths import resolve_concept_path
from .sources import validate_sources_value
from .validation import validate_concept

_RESERVED_IDS = {"index", "log", "bundle"}

_UNSET = object()
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
    resource: str | None,
    sources: Sequence[Mapping[str, Any]],
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
    if resource is not None and (not isinstance(resource, str) or not resource.strip()):
        raise ConfigurationError("concept resource must be a non-empty string")
    if isinstance(sources, str):
        raise ConfigurationError("sources must be a sequence of mappings")
    source_values = list(sources)
    source_findings = validate_sources_value(source_values, path="sources")
    source_errors = [finding for finding in source_findings if finding.severity == "error"]
    if source_errors:
        raise ConfigurationError("; ".join(finding.message for finding in source_errors))
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
    if resource is not None:
        metadata["resource"] = resource
    if source_values:
        metadata["sources"] = [dict(source) for source in source_values]
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
    resource: str | None = None,
    sources: Sequence[Mapping[str, Any]] = (),
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
        resource=resource,
        sources=sources,
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


def _set_optional_metadata(
    metadata: dict[str, Any],
    *,
    concept_type: str | object,
    title: str | object,
    description: str | object,
    tags: Sequence[str] | object,
    status: str | object,
    resource: str | object,
    sources: Sequence[Mapping[str, Any]] | object,
) -> None:
    if concept_type is not _UNSET:
        if not isinstance(concept_type, str) or not concept_type.strip():
            raise ConfigurationError("concept type must be non-empty")
        metadata["type"] = concept_type
    if title is not _UNSET:
        if title is None:
            metadata.pop("title", None)
        elif not isinstance(title, str):
            raise ConfigurationError("concept title must be a string")
        else:
            metadata["title"] = title
    if description is not _UNSET:
        if description is None:
            metadata.pop("description", None)
        elif not isinstance(description, str):
            raise ConfigurationError("concept description must be a string")
        else:
            metadata["description"] = description
    if tags is not _UNSET:
        if isinstance(tags, str):
            raise ConfigurationError("tags must be a sequence of strings")
        try:
            tag_values = list(tags)  # type: ignore[arg-type]
        except TypeError as exc:
            raise ConfigurationError("tags must be a sequence of strings") from exc
        if any(not isinstance(tag, str) or not tag.strip() for tag in tag_values):
            raise ConfigurationError("tags must contain non-empty strings")
        if tag_values:
            metadata["tags"] = tag_values
        else:
            metadata.pop("tags", None)
    if status is not _UNSET:
        if status is None:
            metadata.pop("status", None)
        elif status not in _VALID_STATUS:
            raise ConfigurationError(f"invalid status: {status}")
        else:
            metadata["status"] = status
    if resource is not _UNSET:
        if resource is None:
            metadata.pop("resource", None)
        elif not isinstance(resource, str) or not resource.strip():
            raise ConfigurationError("concept resource must be a non-empty string")
        else:
            metadata["resource"] = resource
    if sources is not _UNSET:
        if isinstance(sources, str):
            raise ConfigurationError("sources must be a sequence of mappings")
        try:
            source_values = list(sources)  # type: ignore[arg-type]
        except TypeError as exc:
            raise ConfigurationError("sources must be a sequence of mappings") from exc
        source_findings = validate_sources_value(source_values, path="sources")
        source_errors = [finding for finding in source_findings if finding.severity == "error"]
        if source_errors:
            raise ConfigurationError("; ".join(finding.message for finding in source_errors))
        metadata["sources"] = [dict(source) for source in source_values]


def update_concept(
    bundle_root: Path,
    concept_id: str,
    *,
    concept_type: str | object = _UNSET,
    title: str | object = _UNSET,
    description: str | object = _UNSET,
    tags: Sequence[str] | object = _UNSET,
    status: str | object = _UNSET,
    resource: str | object = _UNSET,
    sources: Sequence[Mapping[str, Any]] | object = _UNSET,
    body: str | object = _UNSET,
    generated_by: str,
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
    if Path(concept_id).name in _RESERVED_IDS:
        raise ConfigurationError(f"reserved concept ID: {concept_id}")
    target = resolve_concept_path(bundle_root, concept_id)
    if not fs.exists(target):
        raise ConfigurationError(f"concept does not exist: {target}")
    if not fs.is_file(target):
        raise ConfigurationError(f"concept path is not a file: {target}")
    try:
        current = parse_concept(fs.read_text(target))
    except (DocumentError, OSError, UnicodeDecodeError) as exc:
        raise ConfigurationError(f"could not read concept {target}: {exc}") from exc
    _validate_actor(generated_by)

    proposed_metadata = deepcopy(current.metadata)
    _set_optional_metadata(
        proposed_metadata,
        concept_type=concept_type,
        title=title,
        description=description,
        tags=tags,
        status=status,
        resource=resource,
        sources=sources,
    )
    proposed_body = current.body if body is _UNSET else body
    if not isinstance(proposed_body, str):
        raise ConfigurationError("concept body must be text")

    def without_generated(metadata: Mapping[str, Any]) -> dict[str, Any]:
        copy = deepcopy(dict(metadata))
        copy.pop("generated", None)
        return copy

    meaningful = (
        without_generated(proposed_metadata) != without_generated(current.metadata)
        or proposed_body != current.body
    )
    if not meaningful:
        return OperationResult(
            data={"path": str(target), "updated": False},
            changes=fs.changes,
        )

    generated = proposed_metadata.get("generated")
    if not isinstance(generated, Mapping):
        generated = {}
    else:
        generated = deepcopy(dict(generated))
    generated["by"] = generated_by
    generated["at"] = _timestamp(now)
    proposed_metadata["generated"] = generated
    proposed = ConceptDocument(proposed_metadata, proposed_body)
    findings = validate_concept(proposed, path=target, bundle_root=bundle_root)
    errors = [finding for finding in findings if finding.severity == "error"]
    if errors:
        raise ValidationError("; ".join(finding.message for finding in errors))
    warnings = tuple(finding.message for finding in findings if finding.severity == "warning")

    write_if_changed(fs, target, render_concept(proposed))
    if rebuild:
        rebuild_indexes(bundle_root, fs)
    if log_change:
        append_log(
            bundle_root,
            "Update",
            f"Updated {concept_id}.",
            date=(now or datetime.now(timezone.utc)).date(),
            fs=fs,
        )
    return OperationResult(
        data={"path": str(target), "updated": True},
        warnings=warnings,
        changes=fs.changes,
    )
