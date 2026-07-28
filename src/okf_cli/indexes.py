from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .documents import ConceptDocument, parse_concept
from .filesystem import FileSystem

_RESERVED = {"index.md", "log.md"}


def _sort_paths(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda path: (path.name.casefold(), path.name))


def _escape_label(value: object) -> str:
    text = str(value).replace("\\", "\\\\")
    return text.replace("[", "\\[").replace("]", "\\]")


def _title_for(path: Path, metadata: dict[str, Any]) -> str:
    title = metadata.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return path.stem.replace("-", " ").replace("_", " ").title()


def _description_for(metadata: dict[str, Any]) -> str:
    description = metadata.get("description", "")
    if not isinstance(description, str):
        return ""
    return " ".join(description.split())


def _concept_entry(path: Path, directory: Path) -> str:
    document = parse_concept(path.read_text(encoding="utf-8"))
    title = _escape_label(_title_for(path, document.metadata))
    description = _description_for(document.metadata)
    link = path.relative_to(directory).as_posix()
    entry = f"* [{title}]({link})"
    if description:
        entry += f" - {description}"
    return entry


def _group_entry(path: Path, directory: Path) -> str:
    label = _escape_label(path.name)
    link = f"{path.relative_to(directory).as_posix()}/"
    return f"* [{label}]({link})"


def _bundle_metadata(bundle_root: Path) -> dict[str, Any]:
    bundle_document = bundle_root / "bundle.md"
    if not bundle_document.is_file():
        return {}
    return parse_concept(bundle_document.read_text(encoding="utf-8")).metadata


def _resource_link(reference_path: Path, resource: object, catalog_root: Path) -> str:
    if not isinstance(resource, str) or not resource.strip():
        return ""
    resource = resource.strip()
    parsed = urlsplit(resource)
    if parsed.scheme or parsed.netloc:
        return resource
    target = Path(resource)
    if not target.is_absolute():
        target = reference_path.parent / target
    target = target.resolve(strict=False)
    relative = os.path.relpath(target, catalog_root.resolve()).replace(os.sep, "/")
    if relative == ".":
        relative = ""
    if not relative.endswith("/"):
        relative += "/"
    return relative or "./"


def _catalog_entries(bundle_root: Path) -> list[str]:
    references_root = bundle_root / "bundles"
    if not references_root.is_dir():
        return []
    entries: list[tuple[str, str]] = []
    for path in _sort_paths(
        [candidate for candidate in references_root.iterdir() if candidate.is_file() and candidate.suffix == ".md"]
    ):
        if path.name in _RESERVED:
            continue
        document = parse_concept(path.read_text(encoding="utf-8"))
        title = _title_for(path, document.metadata)
        link = _resource_link(path, document.metadata.get("resource"), bundle_root)
        if not link:
            continue
        description = _description_for(document.metadata)
        entry = f"* [{_escape_label(title)}]({link})"
        if description:
            entry += f" - {description}"
        entries.append((title.casefold(), entry))
    return [entry for _, entry in sorted(entries, key=lambda value: value[0])]


def _render_index(
    directory: Path,
    bundle_root: Path,
    *,
    root: bool,
    catalog: bool,
    metadata: dict[str, Any],
) -> str:
    concepts = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix == ".md" and path.name not in _RESERVED
    ]
    concepts = _sort_paths(concepts)
    if root:
        concepts = [path for path in concepts if path.name != "bundle.md"]
    groups = _sort_paths([path for path in directory.iterdir() if path.is_dir() and not path.name.startswith(".")])

    lines: list[str] = []
    if root:
        lines.extend(["---", 'okf_version: "0.2"', "---", ""])
        title = _title_for(bundle_root / "bundle.md", metadata) if metadata else bundle_root.name
        lines.append(f"# {_escape_label(title)}")
        description = _description_for(metadata)
        if description:
            lines.extend(["", description])
        lines.append("")
        if catalog:
            entries = _catalog_entries(bundle_root)
            if entries:
                lines.extend(["# Bundles", "", *entries, ""])
        elif concepts:
            lines.extend(["# Concepts", "", *[_concept_entry(path, directory) for path in concepts], ""])
        if groups and not catalog:
            lines.extend(["# Groups", "", *[_group_entry(path, directory) for path in groups], ""])
    else:
        title = _escape_label(directory.name.replace("-", " ").replace("_", " ").title())
        lines.extend([f"# {title}", ""])
        if concepts:
            lines.extend(["# Concepts", "", *[_concept_entry(path, directory) for path in concepts], ""])
        if groups:
            lines.extend(["# Groups", "", *[_group_entry(path, directory) for path in groups], ""])

    if not lines:
        lines = [""]
    return "\n".join(lines).rstrip("\n") + "\n"


def _directories(bundle_root: Path) -> list[Path]:
    directories = [bundle_root]
    directories.extend(
        sorted(
            (path for path in bundle_root.rglob("*") if path.is_dir() and not path.name.startswith(".")),
            key=lambda path: path.relative_to(bundle_root).as_posix().casefold(),
        )
    )
    return directories


def rebuild_indexes(
    bundle_root: Path,
    fs: FileSystem,
    *,
    catalog: bool = False,
) -> list[Path]:
    bundle_root = Path(bundle_root)
    metadata = _bundle_metadata(bundle_root)
    written: list[Path] = []
    for directory in _directories(bundle_root):
        path = directory / "index.md"
        content = _render_index(
            directory,
            bundle_root,
            root=directory == bundle_root,
            catalog=catalog and directory == bundle_root,
            metadata=metadata,
        )
        fs.write_text(path, content)
        written.append(path)
    return written
