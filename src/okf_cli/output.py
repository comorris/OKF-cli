from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Mapping

from .errors import OkfError


@dataclass(frozen=True)
class CommandResult:
    command: str
    data: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


def render_result(result: CommandResult, format_name: str) -> str:
    if format_name == "json":
        payload = {
            "ok": True,
            "command": result.command,
            "data": dict(result.data),
            "warnings": list(result.warnings),
            "errors": [],
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"

    lines = [result.command]
    for key, value in result.data.items():
        lines.append(f"{key}: {value}")
    for warning in result.warnings:
        lines.append(f"warning: {warning}")
    return "\n".join(lines) + "\n"


def render_error(
    command: str,
    error: OkfError | str,
    format_name: str,
) -> str:
    message = str(error)
    if format_name == "json":
        payload = {
            "ok": False,
            "command": command,
            "data": {},
            "warnings": [],
            "errors": [message],
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"
    return f"error: {message}\n"
