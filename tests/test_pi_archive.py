from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from okf_cli.errors import ConfigurationError
from okf_cli.pi_archive import inventory_archive, iter_session_text


def make_archive(tmp_path: Path, *, extra_member: str | None = None) -> Path:
    archive = tmp_path / "conversations.zip"
    records = [
        {
            "type": "session",
            "id": "session-1",
            "timestamp": "2026-07-27T12:00:00Z",
        },
        {
            "type": "message",
            "id": "message-1",
            "message": {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Implement the durable behavior."},
                    {"type": "toolCall", "arguments": {"secret": "omit"}},
                ],
            },
        },
        {
            "type": "message",
            "id": "message-2",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "I will preserve the interface."}],
            },
        },
    ]
    content = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zipped:
        zipped.writestr("sessions/z.jsonl", content)
        zipped.writestr("sessions/a.jsonl", content.replace("session-1", "session-2"))
        if extra_member is not None:
            zipped.writestr(extra_member, "not a session")
    return archive


def test_archive_inventory_is_sorted_and_includes_sha256_size_and_timestamp(tmp_path: Path) -> None:
    archive = make_archive(tmp_path)

    members = inventory_archive(archive)

    assert [member.member for member in members] == ["sessions/a.jsonl", "sessions/z.jsonl"]
    assert all(member.size > 0 for member in members)
    assert all(len(member.sha256) == 64 for member in members)
    assert all(len(member.archive_sha256) == 64 for member in members)
    assert all(member.timestamp.endswith("Z") for member in members)


def test_archive_reader_never_calls_extract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = make_archive(tmp_path)

    def fail_extract(*args: object, **kwargs: object) -> None:
        raise AssertionError("archive extraction is forbidden")

    monkeypatch.setattr(ZipFile, "extract", fail_extract)
    monkeypatch.setattr(ZipFile, "extractall", fail_extract)

    sessions = list(iter_session_text(archive, max_record_bytes=4096))

    assert len(sessions) == 2


def test_archive_reader_keeps_only_user_and_assistant_text_parts(tmp_path: Path) -> None:
    archive = make_archive(tmp_path)

    sessions = list(iter_session_text(archive, max_record_bytes=4096))

    assert sessions[0].messages == (
        {"role": "user", "text": "Implement the durable behavior."},
        {"role": "assistant", "text": "I will preserve the interface."},
    )


def test_archive_reader_excludes_tool_results_calls_and_thinking_events(tmp_path: Path) -> None:
    archive = tmp_path / "mixed.zip"
    records = [
        {"type": "session", "id": "session-1", "timestamp": "2026-07-27T12:00:00Z"},
        {"type": "thinking_level_change", "thinkingLevel": "high"},
        {
            "type": "message",
            "message": {"role": "toolResult", "content": [{"type": "text", "text": "omit"}]},
        },
        {
            "type": "message",
            "message": {"role": "assistant", "content": [{"type": "toolCall", "name": "omit"}]},
        },
        {
            "type": "message",
            "message": {"role": "user", "content": [{"type": "text", "text": "keep"}]},
        },
    ]
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("session.jsonl", "".join(json.dumps(record) + "\n" for record in records))

    sessions = list(iter_session_text(archive, max_record_bytes=4096))

    assert sessions[0].messages == ({"role": "user", "text": "keep"},)


def test_archive_reader_skips_oversized_jsonl_records_with_diagnostic_count(tmp_path: Path) -> None:
    archive = tmp_path / "oversized.zip"
    oversized = {"type": "message", "message": {"role": "user", "content": [{"type": "text", "text": "x" * 500}]}}
    valid = {"type": "session", "id": "session-1", "timestamp": "2026-07-27T12:00:00Z"}
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("session.jsonl", json.dumps(oversized) + "\n" + json.dumps(valid) + "\n")

    sessions = list(iter_session_text(archive, max_record_bytes=100))

    assert sessions[0].skipped_records == 1
    assert sessions[0].messages == ()
    assert sessions[0].session_id == "session-1"


def test_archive_reader_rejects_non_jsonl_members(tmp_path: Path) -> None:
    archive = make_archive(tmp_path, extra_member="sessions/README.txt")

    with pytest.raises(ConfigurationError):
        list(iter_session_text(archive, max_record_bytes=4096))


def test_archive_output_is_deterministic_across_runs(tmp_path: Path) -> None:
    archive = make_archive(tmp_path)

    first = list(iter_session_text(archive, max_record_bytes=4096))
    second = list(iter_session_text(archive, max_record_bytes=4096))

    assert first == second


def test_script_writes_only_to_explicit_output_outside_bundle(tmp_path: Path) -> None:
    archive = make_archive(tmp_path)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    output = tmp_path / "temporary" / "conversations"
    script = Path(__file__).parents[1] / "scripts" / "extract_pi_archive.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--archive",
            str(archive),
            "--bundle",
            str(bundle),
            "--out",
            str(output),
            "--max-record-bytes",
            "4096",
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert (output / "inventory.json").is_file()
    assert (output / "sessions.jsonl").is_file()
    assert not any(bundle.iterdir())


def test_script_refuses_output_inside_bundle(tmp_path: Path) -> None:
    archive = make_archive(tmp_path)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    output = bundle / "temporary"
    script = Path(__file__).parents[1] / "scripts" / "extract_pi_archive.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--archive",
            str(archive),
            "--bundle",
            str(bundle),
            "--out",
            str(output),
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert not output.exists()
