from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from okf_cli.bundles import init_bundle
from okf_cli.cli import main
from okf_cli.concepts import _UNSET, create_concept, update_concept
from okf_cli.documents import ConceptDocument, parse_concept, render_concept
from okf_cli.errors import ConfigurationError
from okf_cli.filesystem import FileSystem

_NOW = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
_LATER = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)


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


def create(bundle: Path, concept_id: str = "concept", **kwargs: object) -> None:
    values: dict[str, object] = {
        "concept_type": "Reference",
        "title": "Original title",
        "description": "Original description",
        "tags": ("original",),
        "status": "stable",
        "resource": "README.md",
        "sources": ({"id": "readme", "resource": "README.md"},),
        "body": "# Original\n\nOriginal body.\n",
        "generated_by": "test/1.0",
        "force": False,
        "rebuild": True,
        "log_change": True,
        "fs": FileSystem(),
        "now": _NOW,
    }
    values.update(kwargs)
    create_concept(bundle, concept_id, **values)  # type: ignore[arg-type]


def update(bundle: Path, concept_id: str = "concept", **kwargs: object):
    values: dict[str, object] = {
        "concept_type": _UNSET,
        "title": _UNSET,
        "description": _UNSET,
        "tags": _UNSET,
        "status": _UNSET,
        "resource": _UNSET,
        "sources": _UNSET,
        "body": _UNSET,
        "generated_by": "test/1.0",
        "rebuild": True,
        "log_change": True,
        "fs": FileSystem(),
        "now": _LATER,
    }
    values.update(kwargs)
    return update_concept(bundle, concept_id, **values)  # type: ignore[arg-type]


def read_document(bundle: Path, concept_id: str = "concept") -> ConceptDocument:
    return parse_concept((bundle / f"{concept_id}.md").read_text(encoding="utf-8"))


def test_update_requires_existing_concept(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)

    with pytest.raises(ConfigurationError):
        update(bundle, "missing")


def test_update_changes_only_explicit_scalar_fields(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    create(bundle)

    update(bundle, title="Updated title")

    document = read_document(bundle)
    assert document.metadata["type"] == "Reference"
    assert document.metadata["title"] == "Updated title"
    assert document.metadata["description"] == "Original description"
    assert document.metadata["tags"] == ["original"]
    assert document.metadata["status"] == "stable"
    assert document.metadata["resource"] == "README.md"


def test_update_preserves_unknown_frontmatter_fields(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    path = bundle / "concept.md"
    path.write_text(
        render_concept(
            ConceptDocument(
                metadata={
                    "type": "Reference",
                    "title": "Original title",
                    "generated": {"by": "test/1.0", "at": "2026-07-27T12:00:00Z"},
                    "custom_extension": {"owner": "team", "values": [1, 2]},
                    "sources": [
                        {
                            "id": "readme",
                            "resource": "README.md",
                            "extension": {"confidence": "high"},
                        }
                    ],
                },
                body="Body.\n",
            )
        ),
        encoding="utf-8",
    )

    update(bundle, title="Updated title")

    metadata = read_document(bundle).metadata
    assert metadata["custom_extension"] == {"owner": "team", "values": [1, 2]}
    assert metadata["sources"][0]["extension"] == {"confidence": "high"}


def test_update_preserves_body_when_body_option_is_omitted(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    create(bundle)

    update(bundle, title="Updated title")

    assert read_document(bundle).body == "# Original\n\nOriginal body.\n"


def test_update_replaces_body_when_body_file_is_supplied(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    create(bundle)
    body_file = tmp_path / "updated.md"
    body_file.write_text("# Updated\n\nUpdated body.\n", encoding="utf-8")

    code = main(
        [
            "--format",
            "json",
            "concept",
            "update",
            "concept",
            "--bundle",
            str(bundle),
            "--body-file",
            str(body_file),
            "--no-index",
            "--no-log",
        ]
    )

    assert code == 0
    assert read_document(bundle).body == "# Updated\n\nUpdated body.\n"


def test_update_replaces_sources_only_when_sources_file_is_supplied(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    create(bundle)
    sources_file = tmp_path / "sources.yaml"
    sources_file.write_text(
        "- id: design\n  resource: DESIGN.md\n  extension: {reviewed: true}\n",
        encoding="utf-8",
    )

    code = main(
        [
            "--format",
            "json",
            "concept",
            "update",
            "concept",
            "--bundle",
            str(bundle),
            "--sources-file",
            str(sources_file),
            "--no-index",
            "--no-log",
        ]
    )

    assert code == 0
    sources = read_document(bundle).metadata["sources"]
    assert sources == [{"id": "design", "resource": "DESIGN.md", "extension": {"reviewed": True}}]


def test_update_preserves_sources_when_sources_file_is_omitted(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    create(bundle)

    update(bundle, title="Updated title")

    assert read_document(bundle).metadata["sources"] == [{"id": "readme", "resource": "README.md"}]


def test_update_refreshes_generated_only_for_meaningful_change(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    create(bundle)
    original_generated = read_document(bundle).metadata["generated"]

    update(bundle, title="Changed", now=_LATER)
    changed_generated = read_document(bundle).metadata["generated"]
    assert changed_generated["at"] == "2026-07-28T12:00:00Z"
    assert changed_generated != original_generated

    update(bundle, title="Changed", now=datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc))
    assert read_document(bundle).metadata["generated"] == changed_generated


def test_update_noop_writes_no_files_and_adds_no_log(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    create(bundle)
    before = (bundle / "concept.md").read_text(encoding="utf-8")
    log_before = (bundle / "log.md").read_text(encoding="utf-8")
    fs = FileSystem()

    result = update(bundle, title="Original title", fs=fs)

    assert result.data["updated"] is False
    assert result.changes == ()
    assert (bundle / "concept.md").read_text(encoding="utf-8") == before
    assert (bundle / "log.md").read_text(encoding="utf-8") == log_before


def test_update_rebuilds_indexes_and_logs_once(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    create(bundle)

    result = update(bundle, title="Updated title")

    assert result.data["updated"] is True
    assert sum(change.path == bundle / "concept.md" for change in result.changes) == 1
    assert sum(change.path == bundle / "index.md" for change in result.changes) == 1
    assert sum(change.path == bundle / "log.md" for change in result.changes) == 1
    log = (bundle / "log.md").read_text(encoding="utf-8")
    assert log.count("Updated concept.") == 1


def test_update_dry_run_reports_changes_without_writing(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    create(bundle)
    before = (bundle / "concept.md").read_text(encoding="utf-8")
    fs = FileSystem(dry_run=True)

    result = update(bundle, title="Updated title", fs=fs)

    assert result.data["updated"] is True
    assert (bundle / "concept.md").read_text(encoding="utf-8") == before
    assert {change.path for change in result.changes} >= {
        bundle / "concept.md",
        bundle / "index.md",
        bundle / "log.md",
    }


def test_update_cli_json_contract_and_validation(tmp_path: Path, capsys: object) -> None:
    bundle = make_bundle(tmp_path)
    create(bundle)

    code = main(
        [
            "--format",
            "json",
            "concept",
            "update",
            "concept",
            "--bundle",
            str(bundle),
            "--title",
            "Updated title",
            "--status",
            "stable",
            "--no-index",
            "--no-log",
        ]
    )
    payload = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]

    assert code == 0
    assert set(payload) == {"ok", "command", "data", "warnings", "errors"}
    assert payload["ok"] is True
    assert payload["command"] == "concept.update"
    assert payload["data"]["updated"] is True


def test_update_body_and_body_file_are_mutually_exclusive(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    create(bundle)
    body_file = tmp_path / "updated.md"
    body_file.write_text("body", encoding="utf-8")

    code = main(
        [
            "concept",
            "update",
            "concept",
            "--bundle",
            str(bundle),
            "--body",
            "body",
            "--body-file",
            str(body_file),
        ]
    )

    assert code == 2


def test_update_does_not_offer_force_option(tmp_path: Path, capsys: object) -> None:
    bundle = make_bundle(tmp_path)

    code = main(["concept", "update", "--help"])
    help_text = capsys.readouterr().out  # type: ignore[attr-defined]

    assert code == 0
    assert "--force" not in help_text
    assert str(bundle) not in help_text
