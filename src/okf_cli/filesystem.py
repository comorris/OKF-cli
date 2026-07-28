from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlannedChange:
    path: Path
    operation: str
    content: str


class FileSystem:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self._changes: list[PlannedChange] = []
        self._planned_files: dict[Path, str] = {}
        self._planned_dirs: set[Path] = set()

    @property
    def changes(self) -> tuple[PlannedChange, ...]:
        return tuple(self._changes)

    def _record_virtual_parents(self, path: Path) -> None:
        parent = path.parent
        while parent != parent.parent:
            self._planned_dirs.add(parent)
            if parent.exists():
                break
            parent = parent.parent

    def write_text(self, path: Path, content: str) -> None:
        path = Path(path)
        change = PlannedChange(path=path, operation="write", content=content)
        self._changes.append(change)
        self._planned_files[path] = content
        self._record_virtual_parents(path)
        if self.dry_run:
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, path)
            temporary_name = None
        finally:
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass

    def mkdir(self, path: Path) -> None:
        path = Path(path)
        if self.is_dir(path):
            return
        self._changes.append(PlannedChange(path=path, operation="mkdir", content=""))
        self._planned_dirs.add(path)
        self._record_virtual_parents(path)
        if not self.dry_run:
            path.mkdir(parents=True, exist_ok=True)

    def exists(self, path: Path) -> bool:
        path = Path(path)
        return path.exists() or path in self._planned_files or path in self._planned_dirs

    def is_file(self, path: Path) -> bool:
        path = Path(path)
        return path.is_file() or path in self._planned_files

    def is_dir(self, path: Path) -> bool:
        path = Path(path)
        return path.is_dir() or path in self._planned_dirs

    def iterdir(self, path: Path) -> tuple[Path, ...]:
        path = Path(path)
        children: dict[Path, None] = {}
        if path.is_dir():
            children.update({child: None for child in path.iterdir()})
        for child in self._planned_files:
            if child.parent == path:
                children[child] = None
        for child in self._planned_dirs:
            if child.parent == path:
                children[child] = None
        if not children and not self.is_dir(path):
            raise FileNotFoundError(path)
        return tuple(sorted(children, key=lambda child: child.name))

    def read_text(self, path: Path) -> str:
        path = Path(path)
        if path in self._planned_files:
            return self._planned_files[path]
        return path.read_text(encoding="utf-8")
