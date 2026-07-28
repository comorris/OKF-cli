from __future__ import annotations

from pathlib import Path

from okf_cli.documents import ConceptDocument, render_concept
from okf_cli.filesystem import FileSystem
from okf_cli.indexes import rebuild_indexes


def write_concept(path: Path, metadata: dict[str, object], body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_concept(ConceptDocument(metadata, body)), encoding="utf-8")


def test_bundle_root_index_declares_okf_version(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_concept(bundle / "bundle.md", {"type": "Knowledge Bundle", "title": "Demo"})

    rebuild_indexes(bundle, FileSystem())

    index = (bundle / "index.md").read_text(encoding="utf-8")
    assert index.startswith('---\nokf_version: "0.2"\n---\n')


def test_bundle_root_index_lists_bundle_metadata_and_child_groups(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_concept(
        bundle / "bundle.md",
        {
            "type": "Knowledge Bundle",
            "title": "Demo Bundle",
            "description": "A demo knowledge bundle.",
        },
    )
    write_concept(
        bundle / "architecture" / "overview.md",
        {"type": "Reference", "title": "Overview", "description": "System overview."},
    )

    rebuild_indexes(bundle, FileSystem())

    index = (bundle / "index.md").read_text(encoding="utf-8")
    assert "# Demo Bundle" in index
    assert "A demo knowledge bundle." in index
    assert "* [architecture](architecture/)" in index


def test_nested_index_has_no_frontmatter(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    write_concept(bundle / "bundle.md", {"type": "Knowledge Bundle", "title": "Demo"})
    write_concept(bundle / "group" / "concept.md", {"type": "Reference", "title": "Concept"})

    rebuild_indexes(bundle, FileSystem())

    nested = (bundle / "group" / "index.md").read_text(encoding="utf-8")
    assert not nested.startswith("---")


def test_index_entries_are_sorted_and_include_descriptions(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    write_concept(bundle / "bundle.md", {"type": "Knowledge Bundle", "title": "Demo"})
    write_concept(
        bundle / "b.md",
        {"type": "Reference", "title": "Beta", "description": "Beta description."},
    )
    write_concept(
        bundle / "a.md",
        {"type": "Reference", "title": "Alpha", "description": "Alpha description."},
    )

    rebuild_indexes(bundle, FileSystem())

    index = (bundle / "index.md").read_text(encoding="utf-8")
    alpha = index.index("* [Alpha](a.md) - Alpha description.")
    beta = index.index("* [Beta](b.md) - Beta description.")
    assert alpha < beta


def test_index_excludes_reserved_files(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    write_concept(bundle / "bundle.md", {"type": "Knowledge Bundle", "title": "Demo"})
    write_concept(bundle / "concept.md", {"type": "Reference", "title": "Concept"})
    (bundle / "log.md").write_text("# Directory Update Log\n", encoding="utf-8")

    rebuild_indexes(bundle, FileSystem())

    index = (bundle / "index.md").read_text(encoding="utf-8")
    assert "index.md" not in index
    assert "log.md" not in index
    assert "concept.md" in index


def test_catalog_root_index_links_directly_to_registered_bundle_resources(tmp_path: Path) -> None:
    projects = tmp_path / "projects"
    catalog = projects / "okf"
    external = projects / "hermes-fitness" / "okf"
    write_concept(catalog / "bundle.md", {"type": "Knowledge Bundle", "title": "Catalog"})
    write_concept(
        catalog / "bundles" / "hermes-fitness.md",
        {
            "type": "Knowledge Bundle Reference",
            "title": "Hermes Fitness",
            "description": "Fitness knowledge.",
            "resource": "../../hermes-fitness/okf",
        },
    )
    external.mkdir(parents=True)

    rebuild_indexes(catalog, FileSystem(), catalog=True)

    index = (catalog / "index.md").read_text(encoding="utf-8")
    assert "* [Hermes Fitness](../hermes-fitness/okf/) - Fitness knowledge." in index
    assert "bundles/hermes-fitness.md" not in index


def test_rebuilding_indexes_twice_is_byte_identical(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    write_concept(bundle / "bundle.md", {"type": "Knowledge Bundle", "title": "Demo"})
    write_concept(bundle / "group" / "concept.md", {"type": "Reference", "title": "Concept"})

    rebuild_indexes(bundle, FileSystem())
    first = {
        path: path.read_bytes()
        for path in (bundle / "index.md", bundle / "group" / "index.md")
    }

    rebuild_indexes(bundle, FileSystem())
    second = {path: path.read_bytes() for path in first}

    assert second == first
