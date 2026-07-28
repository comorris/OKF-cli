from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from okf_cli.bundles import init_bundle
from okf_cli.cli import main
from okf_cli.concepts import create_concept
from okf_cli.documents import parse_concept
from okf_cli.errors import ConflictError, ConfigurationError
from okf_cli.filesystem import FileSystem

_NOW = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)


def make_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "project" / "okf"
    init_bundle(
        bundle,
        title="Project",
        description="Project knowledge.",
        catalog=None,
        update_gitignore=False,
        now=_NOW,
        fs=FileSystem(),
    )
    return bundle


def create(bundle: Path, concept_id: str, **kwargs: object) -> object:
    values = {
        "concept_type": "Reference",
        "title": None,
        "description": None,
        "tags": (),
        "status": None,
        "body": "",
        "generated_by": "test/1.0",
        "force": False,
        "rebuild": True,
        "log_change": True,
        "fs": FileSystem(),
    }
    values.update(kwargs)
    return create_concept(bundle, concept_id, **values)


def test_concept_create_maps_nested_id_to_markdown_path(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)

    create(bundle, "architecture/system-overview")

    assert (bundle / "architecture" / "system-overview.md").exists()


def test_concept_create_writes_required_and_optional_metadata(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)

    create(
        bundle,
        "concept",
        concept_type="Metric",
        title="A Metric",
        description="A metric description.",
        tags=("fitness", "daily"),
        status="draft",
    )

    metadata = parse_concept((bundle / "concept.md").read_text(encoding="utf-8")).metadata
    assert metadata["type"] == "Metric"
    assert metadata["title"] == "A Metric"
    assert metadata["description"] == "A metric description."
    assert metadata["tags"] == ["fitness", "daily"]
    assert metadata["status"] == "draft"
    assert metadata["generated"]["by"] == "test/1.0"
    assert metadata["generated"]["at"].endswith("Z")


def test_concept_create_accepts_body_text(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)

    create(bundle, "concept", body="# Concept\n\nBody text.\n")

    document = parse_concept((bundle / "concept.md").read_text(encoding="utf-8"))
    assert document.body == "# Concept\n\nBody text.\n"


def test_concept_create_accepts_utf8_body_file(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    body_file = tmp_path / "body.md"
    body_file.write_text("# Café\n\nDéjà vu.\n", encoding="utf-8")

    code = main(
        [
            "--format",
            "json",
            "concept",
            "create",
            "utf8",
            "--bundle",
            str(bundle),
            "--type",
            "Reference",
            "--body-file",
            str(body_file),
            "--no-index",
            "--no-log",
        ]
    )

    assert code == 0
    assert parse_concept((bundle / "utf8.md").read_text(encoding="utf-8")).body == "# Café\n\nDéjà vu.\n"


def test_body_and_body_file_are_mutually_exclusive_usage_error(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    body_file = tmp_path / "body.md"
    body_file.write_text("body", encoding="utf-8")

    code = main(
        [
            "concept",
            "create",
            "conflict",
            "--bundle",
            str(bundle),
            "--type",
            "Reference",
            "--body",
            "body",
            "--body-file",
            str(body_file),
        ]
    )

    assert code == 2


def test_concept_create_rejects_reserved_id(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)

    with pytest.raises(ConfigurationError):
        create(bundle, "index")
    with pytest.raises(ConfigurationError):
        create(bundle, "log")


def test_concept_create_rejects_absolute_parent_and_symlink_escape(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (bundle / "linked").symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("platform cannot create directory symlinks")

    with pytest.raises(ValueError):
        create(bundle, "../outside")
    with pytest.raises(ValueError):
        create(bundle, "/absolute")
    with pytest.raises(ValueError):
        create(bundle, "linked/escaped")


def test_concept_create_conflicts_without_force(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    create(bundle, "concept", body="old")

    with pytest.raises(ConflictError):
        create(bundle, "concept", body="new")


def test_concept_create_force_replaces_atomically(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    create(bundle, "concept", body="old")

    create(bundle, "concept", body="new", force=True)

    assert parse_concept((bundle / "concept.md").read_text(encoding="utf-8")).body == "new"


def test_concept_create_rebuilds_indexes_and_appends_log_by_default(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)

    create(bundle, "architecture/overview", title="Overview", description="System overview.")

    assert (bundle / "architecture" / "index.md").exists()
    assert "architecture/" in (bundle / "index.md").read_text(encoding="utf-8")
    assert "architecture/overview" in (bundle / "log.md").read_text(encoding="utf-8")


def test_concept_create_can_skip_index_and_log(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    original_log = (bundle / "log.md").read_text(encoding="utf-8")

    create(bundle, "architecture/overview", rebuild=False, log_change=False)

    assert not (bundle / "architecture" / "index.md").exists()
    assert (bundle / "log.md").read_text(encoding="utf-8") == original_log


def test_concept_create_dry_run_reports_all_cascading_changes(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    fs = FileSystem(dry_run=True)

    create(bundle, "architecture/overview", fs=fs)

    paths = {change.path for change in fs.changes}
    assert not (bundle / "architecture" / "overview.md").exists()
    assert bundle / "architecture" / "overview.md" in paths
    assert bundle / "architecture" / "index.md" in paths
    assert bundle / "index.md" in paths
    assert bundle / "log.md" in paths


def test_concept_and_log_commands_emit_json_contract(tmp_path: Path, capsys: object) -> None:
    bundle = make_bundle(tmp_path)
    code = main(
        [
            "--format",
            "json",
            "concept",
            "create",
            "concept",
            "--bundle",
            str(bundle),
            "--type",
            "Reference",
            "--no-index",
            "--no-log",
        ]
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert code == 0
    assert set(payload) == {"ok", "command", "data", "warnings", "errors"}
    assert payload["command"] == "concept.create"

    code = main(
        [
            "--format",
            "json",
            "log",
            "add",
            "--bundle",
            str(bundle),
            "--kind",
            "Update",
            "--message",
            "Updated.",
        ]
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert code == 0
    assert set(payload) == {"ok", "command", "data", "warnings", "errors"}
    assert payload["command"] == "log.add"
