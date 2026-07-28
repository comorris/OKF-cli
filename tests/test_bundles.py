from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from okf_cli.bundles import init_bundle
from okf_cli.catalog import init_catalog
from okf_cli.cli import main
from okf_cli.filesystem import FileSystem

_NOW = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)


def git_init(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)


def test_bundle_init_creates_minimal_conformant_tree(tmp_path: Path) -> None:
    bundle = tmp_path / "project" / "okf"

    init_bundle(
        bundle,
        title="Project",
        description="Project knowledge.",
        catalog=None,
        now=_NOW,
        fs=FileSystem(),
        update_gitignore=False,
    )

    assert {
        path.name for path in bundle.iterdir() if path.is_file()
    } == {"bundle.md", "index.md", "log.md"}


def test_bundle_init_adds_root_okf_rule_to_gitignore(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    git_init(project)

    init_bundle(
        project / "okf",
        title="Project",
        description="Project knowledge.",
        catalog=None,
        now=_NOW,
        fs=FileSystem(),
    )

    assert (project / ".gitignore").read_text(encoding="utf-8") == "/okf/\n"


def test_bundle_init_does_not_duplicate_gitignore_rule(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    git_init(project)
    (project / ".gitignore").write_text("dist/\n/okf/\n", encoding="utf-8")

    init_bundle(
        project / "okf",
        title="Project",
        description="Project knowledge.",
        catalog=None,
        now=_NOW,
        fs=FileSystem(),
    )

    assert (project / ".gitignore").read_text(encoding="utf-8").count("/okf/") == 1


def test_bundle_init_can_skip_gitignore(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    git_init(project)

    init_bundle(
        project / "okf",
        title="Project",
        description="Project knowledge.",
        catalog=None,
        now=_NOW,
        fs=FileSystem(),
        update_gitignore=False,
    )

    assert not (project / ".gitignore").exists()


def test_bundle_init_registers_by_default_when_catalog_resolves(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"
    init_catalog(catalog, title="Projects", description="Catalog.", now=_NOW, fs=FileSystem())

    init_bundle(
        tmp_path / "project" / "okf",
        title="Project",
        description="Project knowledge.",
        catalog=catalog,
        now=_NOW,
        fs=FileSystem(),
        update_gitignore=False,
    )

    assert (catalog / "bundles" / "project.md").exists()


def test_bundle_init_can_skip_registration(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"
    init_catalog(catalog, title="Projects", description="Catalog.", now=_NOW, fs=FileSystem())
    bundle = tmp_path / "project" / "okf"

    init_bundle(
        bundle,
        title="Project",
        description="Project knowledge.",
        catalog=catalog,
        register=False,
        now=_NOW,
        fs=FileSystem(),
        update_gitignore=False,
    )

    assert not (catalog / "bundles" / "project.md").exists()


def test_bundle_init_dry_run_reports_changes_and_writes_nothing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    git_init(project)
    bundle = project / "okf"
    fs = FileSystem(dry_run=True)

    init_bundle(
        bundle,
        title="Project",
        description="Project knowledge.",
        catalog=None,
        now=_NOW,
        fs=fs,
    )

    assert not bundle.exists()
    assert not (project / ".gitignore").exists()
    paths = {change.path for change in fs.changes}
    assert bundle / "bundle.md" in paths
    assert bundle / "index.md" in paths
    assert bundle / "log.md" in paths
    assert project / ".gitignore" in paths


def test_catalog_and_bundle_commands_emit_json_contract(tmp_path: Path, capsys: object) -> None:
    catalog = tmp_path / "catalog"
    code = main(
        [
            "--format",
            "json",
            "catalog",
            "init",
            "--catalog",
            str(catalog),
            "--title",
            "Projects",
            "--description",
            "Catalog.",
        ]
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert code == 0
    assert set(payload) == {"ok", "command", "data", "warnings", "errors"}
    assert payload["command"] == "catalog.init"

    code = main(
        [
            "--format",
            "json",
            "bundle",
            "init",
            "--bundle",
            str(tmp_path / "project" / "okf"),
            "--catalog",
            str(catalog),
            "--title",
            "Project",
            "--description",
            "Project knowledge.",
            "--no-gitignore",
        ]
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert code == 0
    assert set(payload) == {"ok", "command", "data", "warnings", "errors"}
    assert payload["command"] == "bundle.init"
