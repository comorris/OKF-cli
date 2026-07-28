from __future__ import annotations

from pathlib import Path

from okf_cli.filesystem import FileSystem


def test_atomic_write_replaces_file_without_partial_content(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "document.md"
    target.parent.mkdir()
    target.write_text("old content", encoding="utf-8")

    FileSystem().write_text(target, "new content")

    assert target.read_text(encoding="utf-8") == "new content"


def test_dry_run_records_write_without_touching_disk(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "document.md"
    fs = FileSystem(dry_run=True)

    fs.write_text(target, "planned content")

    assert not target.exists()
    assert len(fs.changes) == 1
    assert fs.changes[0].path == target
    assert fs.changes[0].operation == "write"
    assert fs.changes[0].content == "planned content"
