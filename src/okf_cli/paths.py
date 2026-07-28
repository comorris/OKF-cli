from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _parts(value: str | Path) -> tuple[str, ...]:
    path = Path(value)
    if path.is_absolute():
        raise ValueError(f"path must be relative: {value}")
    parts = path.parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"path contains an invalid segment: {value}")
    return parts


def contained_path(root: Path, relative: str | Path, *, suffix: str = "") -> Path:
    """Resolve a relative mutation path while rejecting traversal and escapes."""
    root = Path(root).resolve()
    parts = _parts(relative)
    candidate = root.joinpath(*parts)
    if suffix:
        candidate = candidate.with_name(candidate.name + suffix)
    resolved = candidate.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"path escapes bundle root: {relative}")
    return candidate


def resolve_concept_path(bundle_root: Path, concept_id: str) -> Path:
    if concept_id.endswith(".md"):
        raise ValueError("concept IDs must not include the .md suffix")
    return contained_path(bundle_root, concept_id, suffix=".md")


def _ancestors(path: Path) -> Iterable[Path]:
    yield path
    yield from path.parents


def discover_bundle(cwd: Path) -> Path:
    current = Path(cwd).resolve()
    if current.is_file():
        current = current.parent
    for candidate in _ancestors(current):
        if (candidate / ".git").exists():
            return candidate / "okf"
    return current / "okf"
