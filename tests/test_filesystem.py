from __future__ import annotations

from pathlib import Path

import pytest

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


@pytest.mark.parametrize("dry_run", [False, True])
def test_delete_and_recreate_file(tmp_path: Path, dry_run: bool) -> None:
    target = tmp_path / "document.md"
    target.write_text("original", encoding="utf-8")
    fs = FileSystem(dry_run=dry_run)
    fs.remove_file(target)
    assert not fs.exists(target)
    assert not fs.is_file(target)
    assert target not in fs.iterdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        fs.read_text(target)
    with pytest.raises(FileNotFoundError):
        fs.remove_file(target)
    assert target.exists() is dry_run
    fs.write_text(target, "replacement")
    assert fs.exists(target) and fs.is_file(target)
    assert target in fs.iterdir(tmp_path)
    assert fs.read_text(target) == "replacement"
    assert target.read_text() == ("original" if dry_run else "replacement")
    assert [change.operation for change in fs.changes] == ["delete", "write"]


def test_dry_run_deletes_virtual_file(tmp_path: Path) -> None:
    target = tmp_path / "new.md"
    fs = FileSystem(dry_run=True)
    fs.write_text(target, "new")
    fs.remove_file(target)
    assert not fs.exists(target)
    assert not fs.is_file(target)
    assert target not in fs.iterdir(tmp_path)
    assert not target.exists()
