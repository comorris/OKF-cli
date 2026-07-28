from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

import yaml

from .documents import _FrontmatterLoader
from .errors import ConfigurationError
from .validation import Finding, _error, _warning

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SCOPE_PREFIXES = ("scope:", "conversation:", "archive:")


def load_sources_file(path: Path) -> list[dict[str, Any]]:
    """Load a YAML or JSON source list while retaining extension fields."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigurationError(f"could not read sources file {path}: {exc}") from exc
    try:
        value = yaml.load(text, Loader=_FrontmatterLoader)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"could not parse sources file {path}: {exc}") from exc
    if not isinstance(value, list):
        raise ConfigurationError("sources file root must be a list")

    sources: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(value):
        if not isinstance(entry, Mapping):
            raise ConfigurationError(f"source entry {index} must be a mapping")
        copied = dict(entry)
        resource = copied.get("resource")
        if not isinstance(resource, str) or not resource.strip():
            raise ConfigurationError(f"source entry {index} requires a non-empty resource")
        if "id" in copied:
            source_id = copied["id"]
            if not isinstance(source_id, str) or not source_id.strip():
                raise ConfigurationError(f"source entry {index} id must be a non-empty string")
            if source_id in seen_ids:
                raise ConfigurationError(f"duplicate source id: {source_id}")
            seen_ids.add(source_id)
        sources.append(copied)
    return sources


def _valid_date(value: object) -> bool:
    if not isinstance(value, str) or not _DATE_PATTERN.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _looks_like_filesystem_resource(resource: str) -> bool:
    parsed = urlsplit(resource)
    if parsed.scheme or parsed.netloc or resource.startswith(_SCOPE_PREFIXES):
        return False
    path = Path(resource)
    return path.is_absolute() or resource.startswith(".") or bool(path.suffix)


def _source_path(
    resource: str,
    *,
    document_path: Path | str | None,
    bundle_root: Path | None,
) -> Path:
    source = Path(resource).expanduser()
    if source.is_absolute():
        return source
    if document_path is None:
        base = Path(bundle_root or ".")
        return base / source
    document = Path(document_path)
    if not document.is_absolute() and bundle_root is not None:
        document = Path(bundle_root) / document
    return document.parent / source


def _validate_usage_window(value: object, path: str) -> list[Finding]:
    if not isinstance(value, Mapping):
        return [_error("invalid-source-usage-window", path, "usage_window must be a mapping with from and to")]
    start = value.get("from")
    end = value.get("to")
    if not _valid_date(start) or not _valid_date(end):
        return [_error("invalid-source-usage-window", path, "usage_window from and to must be YYYY-MM-DD")]
    if date.fromisoformat(start) > date.fromisoformat(end):
        return [_error("invalid-source-usage-window", path, "usage_window from must not be after to")]
    return []


def validate_sources_value(
    value: object,
    *,
    path: str,
    document_path: Path | str | None = None,
    bundle_root: Path | None = None,
) -> list[Finding]:
    """Validate concept ``sources`` metadata without rejecting extensions."""
    if not isinstance(value, list):
        return [_error("invalid-sources", path, "sources must be a list")]

    findings: list[Finding] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(value):
        entry_path = f"{path}:sources[{index}]"
        if not isinstance(entry, Mapping):
            findings.append(_error("invalid-source-entry", entry_path, "source must be a mapping"))
            continue
        resource = entry.get("resource")
        if not isinstance(resource, str) or not resource.strip():
            findings.append(_error("invalid-source-resource", entry_path, "source requires a non-empty resource"))
        source_id = entry.get("id")
        if source_id is not None:
            if not isinstance(source_id, str) or not source_id.strip():
                findings.append(_error("invalid-source-id", entry_path, "source id must be a non-empty string"))
            elif source_id in seen_ids:
                findings.append(_error("duplicate-source-id", entry_path, f"duplicate source id: {source_id}"))
            else:
                seen_ids.add(source_id)
        usage_count = entry.get("usage_count")
        if usage_count is not None and (
            isinstance(usage_count, bool) or not isinstance(usage_count, int) or usage_count < 0
        ):
            findings.append(_error("invalid-source-usage-count", entry_path, "usage_count must be a non-negative integer"))
        if "last_modified" in entry and not _valid_date(entry["last_modified"]):
            findings.append(_error("invalid-source-last-modified", entry_path, "last_modified must be YYYY-MM-DD"))
        if "usage_window" in entry:
            findings.extend(_validate_usage_window(entry["usage_window"], entry_path))

        if (
            isinstance(resource, str)
            and resource.strip()
            and bundle_root is not None
            and _looks_like_filesystem_resource(resource)
        ):
            candidate = _source_path(
                resource,
                document_path=document_path or path,
                bundle_root=bundle_root,
            )
            if not candidate.is_file():
                findings.append(
                    _warning(
                        "missing-source-resource",
                        entry_path,
                        f"relative source target does not exist: {resource}",
                    )
                )
    return findings
