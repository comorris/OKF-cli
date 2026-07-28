from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .filesystem import PlannedChange


@dataclass(frozen=True)
class OperationResult:
    data: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    changes: tuple[PlannedChange, ...] = ()


def write_if_changed(fs: object, path: object, content: str) -> bool:
    """Write content through FileSystem only when it changes."""
    filesystem = fs
    if filesystem.exists(path) and filesystem.read_text(path) == content:
        return False
    filesystem.write_text(path, content)
    return True
