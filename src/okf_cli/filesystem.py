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

    @property
    def changes(self) -> tuple[PlannedChange, ...]:
        return tuple(self._changes)

    def write_text(self, path: Path, content: str) -> None:
        path = Path(path)
        change = PlannedChange(path=path, operation="write", content=content)
        self._changes.append(change)
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

    def read_text(self, path: Path) -> str:
        return Path(path).read_text(encoding="utf-8")
