from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, Mapping
from urllib.parse import unquote, urlsplit

from .documents import ConceptDocument, DocumentError, parse_frontmatter


@dataclass(frozen=True)
class Finding:
    severity: Literal["error", "warning"]
    code: str
    path: str
    message: str


def _error(code: str, path: str, message: str) -> Finding:
    return Finding("error", code, path, message)


def _warning(code: str, path: str, message: str) -> Finding:
    return Finding("warning", code, path, message)


def _iso_datetime(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _validate_verified(metadata: Mapping[str, Any], path: str) -> list[Finding]:
    findings: list[Finding] = []
    if "verified" not in metadata:
        return findings
    value = metadata["verified"]
    events = [value] if isinstance(value, Mapping) else value
    if not isinstance(events, list):
        return [_error("invalid-verified", path, "verified must be a mapping or list")]
    for index, event in enumerate(events):
        event_path = f"{path}:verified[{index}]"
        if not isinstance(event, Mapping):
            findings.append(_error("invalid-verified", event_path, "verification event must be a mapping"))
            continue
        if not isinstance(event.get("by"), str) or not str(event["by"]).strip():
            findings.append(_error("invalid-verified", event_path, "verification event requires by"))
        if not _iso_datetime(event.get("at")):
            findings.append(_error("invalid-verified", event_path, "verification event requires ISO at"))
    return findings


def _validate_generated(metadata: Mapping[str, Any], path: str) -> list[Finding]:
    if "generated" not in metadata:
        return []
    value = metadata["generated"]
    if not isinstance(value, Mapping):
        return [_error("invalid-generated", path, "generated must be a mapping")]
    findings: list[Finding] = []
    if not isinstance(value.get("by"), str) or not str(value["by"]).strip():
        findings.append(_error("invalid-generated", path, "generated requires by"))
    if not _iso_datetime(value.get("at")):
        findings.append(_error("invalid-generated", path, "generated requires ISO at"))
    return findings


def _validate_staleness(
    metadata: Mapping[str, Any], path: str, today: date
) -> list[Finding]:
    if "stale_after" not in metadata:
        return []
    value = metadata["stale_after"]
    if isinstance(value, date) and not isinstance(value, datetime):
        stale_after = value
    elif isinstance(value, str):
        try:
            stale_after = date.fromisoformat(value)
        except ValueError:
            return [_error("invalid-stale-after", path, "stale_after must be YYYY-MM-DD")]
    else:
        return [_error("invalid-stale-after", path, "stale_after must be YYYY-MM-DD")]
    if today >= stale_after:
        return [_warning("stale-concept", path, f"concept is stale after {stale_after.isoformat()}")]
    return []


_LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]*\]\((?:<([^>]+)>|([^\s)]+))\)")


def _validate_links(
    document: ConceptDocument,
    path: Path | str,
    bundle_root: Path | None,
) -> list[Finding]:
    if bundle_root is None:
        return []
    path = Path(path)
    root = Path(bundle_root).resolve()
    source = path if path.is_absolute() else root / path
    findings: list[Finding] = []
    for match in _LINK_PATTERN.finditer(document.body):
        target = match.group(1) or match.group(2) or ""
        target = unquote(target.split("#", 1)[0])
        if not target:
            continue
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        if target.startswith("/"):
            candidate = root / target.lstrip("/")
        else:
            candidate = source.parent / target
        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            resolved = candidate.absolute()
        if resolved != root and root not in resolved.parents:
            exists = False
        else:
            exists = candidate.exists()
        if not exists:
            findings.append(_warning("broken-link", str(path), f"link target does not exist: {target}"))
    return findings


def validate_concept(
    document: ConceptDocument,
    *,
    path: Path | str,
    bundle_root: Path | None = None,
    today: date | None = None,
) -> list[Finding]:
    path_text = str(path)
    metadata = document.metadata
    findings: list[Finding] = []
    concept_type = metadata.get("type")
    if not isinstance(concept_type, str) or not concept_type.strip():
        findings.append(_error("missing-type", path_text, "concept type must be a non-empty string"))
    if concept_type == "Attested Computation":
        runtime = metadata.get("runtime")
        if not isinstance(runtime, str) or not runtime.strip():
            findings.append(_error("missing-runtime", path_text, "Attested Computation requires runtime"))
    findings.extend(_validate_generated(metadata, path_text))
    findings.extend(_validate_verified(metadata, path_text))
    findings.extend(_validate_staleness(metadata, path_text, today or date.today()))
    findings.extend(_validate_links(document, path, bundle_root))
    return findings


def _frontmatter_if_present(text: str) -> tuple[dict[str, Any] | None, str]:
    if not text.startswith("---"):
        return None, text
    return parse_frontmatter(text)


def validate_index(text: str, *, root: bool, path: str) -> list[Finding]:
    findings: list[Finding] = []
    try:
        metadata, _body = _frontmatter_if_present(text)
    except DocumentError as exc:
        return [_error("invalid-index-frontmatter", path, str(exc))]
    if metadata is None:
        return findings
    if not root:
        findings.append(_error("nested-index-frontmatter", path, "nested indexes must not have frontmatter"))
        return findings
    if set(metadata) != {"okf_version"}:
        findings.append(
            _error("invalid-root-index-frontmatter", path, "root index frontmatter may contain only okf_version")
        )
    if metadata.get("okf_version") != "0.2":
        findings.append(_error("invalid-okf-version", path, "root index okf_version must be 0.2"))
    return findings


_LOG_DATE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$")
_LOG_LEVEL = re.compile(r"^##(?:\s|$)")


def validate_log(text: str, *, path: str) -> list[Finding]:
    findings: list[Finding] = []
    previous: date | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not _LOG_LEVEL.match(line):
            continue
        match = _LOG_DATE.match(line)
        if match is None:
            findings.append(
                _error("invalid-log-date", f"{path}:{line_number}", "log date headings must use YYYY-MM-DD")
            )
            continue
        current = date.fromisoformat(match.group(1))
        if previous is not None and current > previous:
            findings.append(_error("log-order", path, "log date headings must be newest first"))
        previous = current
    return findings
