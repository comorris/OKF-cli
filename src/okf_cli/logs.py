from __future__ import annotations

import re
from datetime import date as Date, datetime
from pathlib import Path

from .filesystem import FileSystem
from .validation import validate_log

_VALID_KINDS = frozenset({"Initialization", "Creation", "Update", "Deprecation"})
_DATE_HEADING = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$")


def _read_groups(text: str) -> dict[Date, list[str]]:
    findings = [finding for finding in validate_log(text, path="log.md") if finding.severity == "error"]
    if findings:
        raise ValueError(findings[0].message)

    groups: dict[Date, list[str]] = {}
    current: Date | None = None
    for line in text.splitlines():
        match = _DATE_HEADING.match(line)
        if match:
            current = Date.fromisoformat(match.group(1))
            groups.setdefault(current, [])
        elif current is not None and line.strip():
            groups[current].append(line)
    return groups


def _render_groups(groups: dict[Date, list[str]]) -> str:
    lines = ["# Directory Update Log", ""]
    for current in sorted(groups, reverse=True):
        lines.append(f"## {current.isoformat()}")
        lines.extend(groups[current])
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def append_log(
    scope: Path,
    kind: str,
    message: str,
    *,
    date: Date,
    fs: FileSystem,
) -> Path:
    scope = Path(scope)
    if not isinstance(date, Date) or isinstance(date, datetime):
        raise ValueError("log date must be a date")
    if kind not in _VALID_KINDS:
        raise ValueError(f"invalid log kind: {kind}")
    if not message.strip() or "\n" in message or "\r" in message:
        raise ValueError("log message must be a non-empty single line")
    if not fs.is_dir(scope) and not (fs.dry_run and not fs.exists(scope)):
        raise ValueError(f"log scope must be a directory: {scope}")

    log_path = scope / "log.md"
    existing = fs.read_text(log_path) if fs.is_file(log_path) else ""
    groups = _read_groups(existing) if existing else {}
    groups.setdefault(date, []).append(f"* **{kind}**: {message.strip()}")
    content = _render_groups(groups)
    fs.write_text(log_path, content)
    return log_path
