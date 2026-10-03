from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from okf_cli.catalog import init_catalog, list_bundles, register_bundle, unregister_bundle
from okf_cli.documents import ConceptDocument, parse_concept, render_concept
from okf_cli.errors import ConfigurationError
from okf_cli.filesystem import FileSystem

_NOW = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)


def write_bundle(path: Path, title: str, description: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "bundle.md").write_text(
        render_concept(
            ConceptDocument(
                {
                    "type": "Knowledge Bundle",
                    "title": title,
                    "description": description,
                    "status": "stable",
                    "generated": {"by": "test/1.0", "at": "2026-07-27T12:00:00Z"},
                },
                "",
            )
        ),
        encoding="utf-8",
    )


def test_catalog_init_creates_minimal_conformant_tree(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"

    init_catalog(
        catalog,
        title="Projects",
        description="Project catalog.",
        generated_by="test/1.0",
        now=_NOW,
        fs=FileSystem(),
    )

    assert {
        path.relative_to(catalog).as_posix()
        for path in catalog.rglob("*")
        if path.is_file()
    } == {"bundle.md", "index.md", "log.md", "bundles/index.md"}
    bundle = parse_concept((catalog / "bundle.md").read_text(encoding="utf-8"))
    assert bundle.metadata["type"] == "Knowledge Bundle"
    assert (catalog / "bundles" / "index.md").exists()


def test_catalog_init_is_idempotent(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"
    init_catalog(catalog, title="Projects", description="Project catalog.", now=_NOW, fs=FileSystem())
    first = {path: path.read_bytes() for path in catalog.rglob("*") if path.is_file()}

    second_fs = FileSystem()
    init_catalog(catalog, title="Projects", description="Project catalog.", now=_NOW, fs=second_fs)

    assert {path: path.read_bytes() for path in catalog.rglob("*") if path.is_file()} == first
    assert second_fs.changes == ()


def test_register_writes_relative_resource_when_possible(tmp_path: Path) -> None:
    catalog = tmp_path / "projects" / "catalog"
    bundle = tmp_path / "projects" / "hermes-fitness" / "okf"
    init_catalog(catalog, title="Projects", description="Catalog.", now=_NOW, fs=FileSystem())
    write_bundle(bundle, "Hermes Fitness", "Fitness knowledge.")

    register_bundle(catalog, bundle, now=_NOW, fs=FileSystem())

    reference = parse_concept(
        (catalog / "bundles" / "hermes-fitness.md").read_text(encoding="utf-8")
    )
    assert reference.metadata["resource"] == "../../hermes-fitness/okf"


def test_register_same_bundle_twice_does_not_duplicate_reference(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"
    bundle = tmp_path / "project" / "okf"
    init_catalog(catalog, title="Projects", description="Catalog.", now=_NOW, fs=FileSystem())
    write_bundle(bundle, "Project", "Project knowledge.")

    register_bundle(catalog, bundle, now=_NOW, fs=FileSystem())
    second_fs = FileSystem()
    register_bundle(catalog, bundle, now=_NOW, fs=second_fs)

    references = [
        path for path in (catalog / "bundles").glob("*.md") if path.name != "index.md"
    ]
    assert [path.name for path in references] == ["project.md"]
    assert second_fs.changes == ()


def test_register_rejects_missing_or_invalid_bundle_metadata(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"
    init_catalog(catalog, title="Projects", description="Catalog.", now=_NOW, fs=FileSystem())

    with pytest.raises(ConfigurationError):
        register_bundle(catalog, tmp_path / "missing", now=_NOW, fs=FileSystem())

    invalid = tmp_path / "invalid"
    invalid.mkdir()
    (invalid / "bundle.md").write_text(
        render_concept(ConceptDocument({"type": "Reference"}, "")), encoding="utf-8"
    )
    with pytest.raises(ConfigurationError):
        register_bundle(catalog, invalid, now=_NOW, fs=FileSystem())


def test_unregister_missing_target_dry_run_and_apply_preserve_other_bundles(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"
    missing = tmp_path / "deleted" / "okf"
    current = tmp_path / "current" / "okf"
    init_catalog(catalog, title="Projects", description="Catalog.", now=_NOW, fs=FileSystem())
    write_bundle(missing, "Project", "Old knowledge.")
    write_bundle(current, "Project", "Current knowledge.")
    register_bundle(catalog, missing, now=_NOW, fs=FileSystem())
    register_bundle(catalog, current, now=_NOW, fs=FileSystem())
    missing_reference = catalog / "bundles" / "project.md"
    current_reference = catalog / "bundles" / "project-2.md"
    current_content = current_reference.read_bytes()
    before = {p: p.read_bytes() for p in catalog.rglob("*") if p.is_file()}
    # The target's parent is gone, like a deleted worktree.
    (missing / "bundle.md").unlink()
    missing.rmdir()
    missing.parent.rmdir()

    preview_fs = FileSystem(dry_run=True)
    preview = unregister_bundle(catalog, missing, now=_NOW, fs=preview_fs)
    assert preview.data == {"bundle": str(missing), "unregistered": True, "paths": [str(missing_reference)]}
    assert any(c.operation == "delete" and c.path == missing_reference for c in preview.changes)
    assert {p: p.read_bytes() for p in catalog.rglob("*") if p.is_file()} == before
    assert "../deleted/okf/" not in preview_fs.read_text(catalog / "index.md")
    assert "../current/okf/" in preview_fs.read_text(catalog / "index.md")

    applied = unregister_bundle(catalog, missing, now=_NOW, fs=FileSystem())
    assert [(c.operation, c.path) for c in applied.changes] == [
        (c.operation, c.path) for c in preview.changes
    ]
    assert not missing_reference.exists()
    assert current_reference.read_bytes() == current_content
    assert "../deleted/okf/" not in (catalog / "index.md").read_text()
    assert "../current/okf/" in (catalog / "index.md").read_text()
    assert "Unregistered bundle" in (catalog / "log.md").read_text()
    assert not missing.exists()

    snapshot = {p: p.read_bytes() for p in catalog.rglob("*") if p.is_file()}
    second = unregister_bundle(catalog, missing, now=_NOW, fs=FileSystem())
    assert second.data["unregistered"] is False
    assert second.changes == ()
    assert {p: p.read_bytes() for p in catalog.rglob("*") if p.is_file()} == snapshot


def test_unregister_removes_all_matching_references_and_rejects_invalid_records(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"
    target = tmp_path / "project" / "okf"
    init_catalog(catalog, title="Projects", description="Catalog.", now=_NOW, fs=FileSystem())
    write_bundle(target, "Project", "Knowledge.")
    register_bundle(catalog, target, now=_NOW, fs=FileSystem())
    duplicate = catalog / "bundles" / "duplicate.md"
    duplicate.write_bytes((catalog / "bundles" / "project.md").read_bytes())
    result = unregister_bundle(catalog, target, now=_NOW, fs=FileSystem(dry_run=True))
    assert result.data["paths"] == [str(duplicate), str(catalog / "bundles" / "project.md")]

    valid_duplicate = duplicate.read_bytes()
    duplicate.write_text("invalid document", encoding="utf-8")
    before = (catalog / "bundles" / "project.md").read_bytes()
    with pytest.raises(ConfigurationError):
        unregister_bundle(catalog, target, now=_NOW, fs=FileSystem())
    assert (catalog / "bundles" / "project.md").read_bytes() == before
    duplicate.write_bytes(valid_duplicate)
    applied = unregister_bundle(catalog, target, now=_NOW, fs=FileSystem())
    assert applied.data == result.data
    assert not duplicate.exists()
    assert not (catalog / "bundles" / "project.md").exists()
    assert (target / "bundle.md").exists()


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("link_kind", ["dangling", "reference", "directory"])
def test_unregister_rejects_symlinks_before_mutation(tmp_path: Path, dry_run: bool, link_kind: str) -> None:
    catalog = tmp_path / "catalog"
    target = tmp_path / "project" / "okf"
    init_catalog(catalog, title="Projects", description="Catalog.", now=_NOW, fs=FileSystem())
    write_bundle(target, "Project", "Knowledge.")
    register_bundle(catalog, target, now=_NOW, fs=FileSystem())
    reference = catalog / "bundles" / "project.md"
    content = reference.read_bytes()
    if link_kind == "directory":
        external = tmp_path / "external"
        (catalog / "bundles").rename(external)
        (catalog / "bundles").symlink_to(external, target_is_directory=True)
    elif link_kind == "reference":
        external = tmp_path / "external.md"
        external.write_bytes(content)
        reference.unlink()
        reference.symlink_to(external)
    else:
        (catalog / "bundles" / "broken.md").symlink_to(tmp_path / "missing.md")
    before = {p: p.read_bytes() for p in catalog.rglob("*") if p.is_file()}
    with pytest.raises(ConfigurationError, match="symlink"):
        unregister_bundle(catalog, target, now=_NOW, fs=FileSystem(dry_run=dry_run))
    assert reference.read_bytes() == content
    assert {p: p.read_bytes() for p in catalog.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("dry_run", [False, True])
def test_unregister_rejects_output_directory_without_mutation(tmp_path: Path, dry_run: bool) -> None:
    catalog = tmp_path / "catalog"
    target = tmp_path / "project" / "okf"
    init_catalog(catalog, title="Projects", description="Catalog.", now=_NOW, fs=FileSystem())
    write_bundle(target, "Project", "Knowledge.")
    register_bundle(catalog, target, now=_NOW, fs=FileSystem())
    (catalog / "log.md").unlink()
    (catalog / "log.md").mkdir()
    before = {p: p.read_bytes() for p in catalog.rglob("*") if p.is_file()}
    with pytest.raises(ConfigurationError, match="output path is a directory"):
        unregister_bundle(catalog, target, now=_NOW, fs=FileSystem(dry_run=dry_run))
    assert {p: p.read_bytes() for p in catalog.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("bad_path", ["log.md", "bundle.md", "notes/bad.md"])
def test_unregister_preflights_all_output_before_deleting(tmp_path: Path, bad_path: str) -> None:
    catalog = tmp_path / "catalog"
    target = tmp_path / "project" / "okf"
    init_catalog(catalog, title="Projects", description="Catalog.", now=_NOW, fs=FileSystem())
    write_bundle(target, "Project", "Knowledge.")
    register_bundle(catalog, target, now=_NOW, fs=FileSystem())
    broken = catalog / bad_path
    broken.parent.mkdir(exist_ok=True)
    broken.write_text("## invalid date\n" if bad_path == "log.md" else "invalid document", encoding="utf-8")
    before = {p: p.read_bytes() for p in catalog.rglob("*") if p.is_file()}
    with pytest.raises(ValueError):
        unregister_bundle(catalog, target, now=_NOW, fs=FileSystem())
    assert {p: p.read_bytes() for p in catalog.rglob("*") if p.is_file()} == before


def test_bundle_list_is_sorted_and_returns_title_description_and_path(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"
    init_catalog(catalog, title="Projects", description="Catalog.", now=_NOW, fs=FileSystem())
    first = tmp_path / "first" / "okf"
    second = tmp_path / "second" / "okf"
    write_bundle(first, "Zulu", "Z description.")
    write_bundle(second, "Alpha", "A description.")
    register_bundle(catalog, first, now=_NOW, fs=FileSystem())
    register_bundle(catalog, second, now=_NOW, fs=FileSystem())

    bundles = list_bundles(catalog)

    assert [bundle["title"] for bundle in bundles] == ["Alpha", "Zulu"]
    assert bundles[0]["description"] == "A description."
    assert Path(bundles[0]["path"]) == second.resolve()
    assert set(bundles[0]) == {"title", "description", "path"}
