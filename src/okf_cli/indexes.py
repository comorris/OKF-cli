from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .documents import parse_concept
from .filesystem import FileSystem
from .operations import write_if_changed

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


def _concept_entry(path: Path, directory: Path, fs: FileSystem) -> str:
    document = parse_concept(fs.read_text(path))
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


def _bundle_metadata(bundle_root: Path, fs: FileSystem) -> dict[str, Any]:
    bundle_document = bundle_root / "bundle.md"
    if not fs.is_file(bundle_document):
        return {}
    return parse_concept(fs.read_text(bundle_document)).metadata


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


def _catalog_entries(bundle_root: Path, fs: FileSystem) -> list[str]:
    references_root = bundle_root / "bundles"
    if not fs.is_dir(references_root):
        return []
    references = [
        candidate
        for candidate in fs.iterdir(references_root)
        if fs.is_file(candidate) and candidate.suffix == ".md" and candidate.name not in _RESERVED
    ]
    entries: list[tuple[str, str]] = []
    for path in _sort_paths(references):
        document = parse_concept(fs.read_text(path))
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
    fs: FileSystem,
    *,
    root: bool,
    catalog: bool,
    metadata: dict[str, Any],
) -> str:
    concepts = [
        path
        for path in fs.iterdir(directory)
        if fs.is_file(path) and path.suffix == ".md" and path.name not in _RESERVED
    ]
    concepts = _sort_paths(concepts)
    if root:
        concepts = [path for path in concepts if path.name != "bundle.md"]
    groups = _sort_paths(
        [path for path in fs.iterdir(directory) if fs.is_dir(path) and not path.name.startswith(".")]
    )

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
            entries = _catalog_entries(bundle_root, fs)
            if entries:
                lines.extend(["# Bundles", "", *entries, ""])
        elif concepts:
            lines.extend(["# Concepts", "", *[_concept_entry(path, directory, fs) for path in concepts], ""])
        if groups and not catalog:
            lines.extend(["# Groups", "", *[_group_entry(path, directory) for path in groups], ""])
    else:
        title = _escape_label(directory.name.replace("-", " ").replace("_", " ").title())
        lines.extend([f"# {title}", ""])
        if concepts:
            lines.extend(["# Concepts", "", *[_concept_entry(path, directory, fs) for path in concepts], ""])
        if groups:
            lines.extend(["# Groups", "", *[_group_entry(path, directory) for path in groups], ""])

    if not lines:
        lines = [""]
    return "\n".join(lines).rstrip("\n") + "\n"


def _directories(bundle_root: Path, fs: FileSystem) -> list[Path]:
    directories: list[Path] = []
    pending = [bundle_root]
    seen: set[Path] = set()
    while pending:
        directory = pending.pop(0)
        if directory in seen or not fs.is_dir(directory):
            continue
        seen.add(directory)
        directories.append(directory)
        children = [
            path
            for path in fs.iterdir(directory)
            if fs.is_dir(path) and not path.name.startswith(".")
        ]
        pending.extend(_sort_paths(children))
    return directories


def rebuild_indexes(
    bundle_root: Path,
    fs: FileSystem,
    *,
    catalog: bool = False,
) -> list[Path]:
    bundle_root = Path(bundle_root)
    metadata = _bundle_metadata(bundle_root, fs)
    written: list[Path] = []
    for directory in _directories(bundle_root, fs):
        path = directory / "index.md"
        content = _render_index(
            directory,
            bundle_root,
            fs,
            root=directory == bundle_root,
            catalog=catalog and directory == bundle_root,
            metadata=metadata,
        )
        write_if_changed(fs, path, content)
        written.append(path)
    return written
