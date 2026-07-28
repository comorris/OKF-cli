from __future__ import annotations

import hashlib
import json
import posixpath
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator
from zipfile import BadZipFile, ZipFile

from .errors import ConfigurationError


@dataclass(frozen=True)
class ArchiveMember:
    member: str
    size: int
    sha256: str
    timestamp: str
    archive_sha256: str
    zip_name: str


@dataclass(frozen=True)
class SessionText:
    member: str
    session_id: str
    session_timestamp: str | None
    archive_sha256: str
    member_sha256: str
    member_size: int
    skipped_records: int
    messages: tuple[dict[str, str], ...]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ConfigurationError(f"could not read archive {path}: {exc}") from exc
    return digest.hexdigest()


def _normalize_member(name: str) -> str:
    normalized = posixpath.normpath(PurePosixPath(name.replace("\\", "/")).as_posix())
    if normalized in {"", "."} or normalized.startswith("../") or normalized == "..":
        raise ConfigurationError(f"unsafe archive member path: {name}")
    return normalized


def _member_sha256(zipped: ZipFile, name: str) -> str:
    digest = hashlib.sha256()
    with zipped.open(name, "r") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_timestamp(info: object) -> str:
    date_time = info.date_time  # type: ignore[attr-defined]
    return datetime(*date_time, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def inventory_archive(path: Path) -> list[ArchiveMember]:
    """Inventory JSONL members without extracting any archive content."""
    path = Path(path)
    archive_sha256 = _sha256_file(path)
    members: list[ArchiveMember] = []
    seen: set[str] = set()
    try:
        with ZipFile(path) as zipped:
            for info in zipped.infolist():
                if info.is_dir():
                    continue
                member = _normalize_member(info.filename)
                if not member.endswith(".jsonl"):
                    raise ConfigurationError(f"archive member is not JSONL: {member}")
                if member in seen:
                    raise ConfigurationError(f"duplicate normalized archive member: {member}")
                seen.add(member)
                members.append(
                    ArchiveMember(
                        member=member,
                        size=info.file_size,
                        sha256=_member_sha256(zipped, info.filename),
                        timestamp=_zip_timestamp(info),
                        archive_sha256=archive_sha256,
                        zip_name=info.filename,
                    )
                )
    except BadZipFile as exc:
        raise ConfigurationError(f"invalid ZIP archive {path}: {exc}") from exc
    return sorted(members, key=lambda item: (item.member.casefold(), item.member))


def _text_from_message(event: dict[str, Any]) -> dict[str, str] | None:
    message = event.get("message")
    if not isinstance(message, dict) or message.get("role") not in {"user", "assistant"}:
        return None
    content = message.get("content")
    parts: list[str] = []
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                parts.append(part["text"])
    if not parts:
        return None
    return {"role": message["role"], "text": "".join(parts)}


def _session_from_member(
    zipped: ZipFile,
    member: ArchiveMember,
    *,
    max_record_bytes: int,
) -> SessionText:
    if max_record_bytes <= 0:
        raise ConfigurationError("max_record_bytes must be positive")
    member_digest = hashlib.sha256()
    session_id = Path(member.member).stem
    session_timestamp: str | None = None
    messages: list[dict[str, str]] = []
    skipped_records = 0

    with zipped.open(member.zip_name, "r") as stream:
        def read_line() -> bytes:
            line = stream.readline(max_record_bytes + 1)
            member_digest.update(line)
            return line

        while True:
            line = read_line()
            if not line:
                break
            if len(line) > max_record_bytes:
                skipped_records += 1
                while line and not line.endswith(b"\n"):
                    line = read_line()
                continue
            try:
                event = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                skipped_records += 1
                continue
            if not isinstance(event, dict):
                skipped_records += 1
                continue
            if event.get("type") == "session":
                if isinstance(event.get("id"), str) and event["id"].strip():
                    session_id = event["id"]
                if isinstance(event.get("timestamp"), str):
                    session_timestamp = event["timestamp"]
                continue
            if event.get("type") != "message":
                continue
            text = _text_from_message(event)
            if text is not None:
                messages.append(text)

    return SessionText(
        member=member.member,
        session_id=session_id,
        session_timestamp=session_timestamp,
        archive_sha256=member.archive_sha256,
        member_sha256=member_digest.hexdigest(),
        member_size=member.size,
        skipped_records=skipped_records,
        messages=tuple(messages),
    )


def iter_session_text(path: Path, *, max_record_bytes: int) -> Iterator[SessionText]:
    """Yield bounded, filtered session text in deterministic member order."""
    if max_record_bytes <= 0:
        raise ConfigurationError("max_record_bytes must be positive")
    members = inventory_archive(Path(path))
    try:
        with ZipFile(path) as zipped:
            for member in members:
                yield _session_from_member(
                    zipped,
                    member,
                    max_record_bytes=max_record_bytes,
                )
    except BadZipFile as exc:
        raise ConfigurationError(f"invalid ZIP archive {path}: {exc}") from exc
