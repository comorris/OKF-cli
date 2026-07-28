from __future__ import annotations

from datetime import date
from pathlib import Path

from okf_cli.bundles import init_bundle
from okf_cli.filesystem import FileSystem
from okf_cli.logs import add_log


def test_log_add_targets_root_or_valid_nested_scope(tmp_path: Path) -> None:
    bundle = tmp_path / "project" / "okf"
    init_bundle(
        bundle,
        title="Project",
        description="Project knowledge.",
        catalog=None,
        update_gitignore=False,
        fs=FileSystem(),
    )
    (bundle / "architecture").mkdir()

    add_log(
        bundle,
        scope="",
        kind="Update",
        message="Root update.",
        date=date(2026, 7, 27),
        fs=FileSystem(),
    )
    add_log(
        bundle,
        scope="architecture",
        kind="Creation",
        message="Architecture created.",
        date=date(2026, 7, 27),
        fs=FileSystem(),
    )

    assert "Root update." in (bundle / "log.md").read_text(encoding="utf-8")
    assert "Architecture created." in (bundle / "architecture" / "log.md").read_text(encoding="utf-8")
