from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from okf_cli.catalog import init_catalog, list_bundles, register_bundle
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
