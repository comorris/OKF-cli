from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from okf_cli.filesystem import FileSystem
from okf_cli.logs import append_log


def test_append_log_creates_valid_root_log(tmp_path: Path) -> None:
    log_path = append_log(
        tmp_path,
        "Initialization",
        "Created the bundle.",
        date=date(2026, 7, 27),
        fs=FileSystem(),
    )

    assert log_path == tmp_path / "log.md"
    assert log_path.read_text(encoding="utf-8") == (
        "# Directory Update Log\n\n"
        "## 2026-07-27\n"
        "* **Initialization**: Created the bundle.\n"
    )


def test_append_log_places_newer_date_first(tmp_path: Path) -> None:
    append_log(tmp_path, "Update", "Older.", date=date(2026, 7, 26), fs=FileSystem())

    append_log(tmp_path, "Update", "Newer.", date=date(2026, 7, 27), fs=FileSystem())

    content = (tmp_path / "log.md").read_text(encoding="utf-8")
    assert content.index("## 2026-07-27") < content.index("## 2026-07-26")


def test_append_log_groups_entries_on_same_date(tmp_path: Path) -> None:
    append_log(tmp_path, "Update", "First.", date=date(2026, 7, 27), fs=FileSystem())

    append_log(tmp_path, "Creation", "Second.", date=date(2026, 7, 27), fs=FileSystem())

    content = (tmp_path / "log.md").read_text(encoding="utf-8")
    assert content.count("## 2026-07-27") == 1
    assert content.index("First.") < content.index("Second.")


def test_append_log_rejects_invalid_kind_or_scope_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        append_log(tmp_path, "Unknown", "Message.", date=date(2026, 7, 27), fs=FileSystem())

    file_scope = tmp_path / "concept.md"
    file_scope.write_text("not a directory", encoding="utf-8")
    with pytest.raises(ValueError):
        append_log(file_scope, "Update", "Message.", date=date(2026, 7, 27), fs=FileSystem())
