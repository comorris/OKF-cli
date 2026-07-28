from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    USAGE = 2
    CONFIGURATION = 3
    CONFLICT = 4
    VALIDATION = 5
    OPERATIONAL = 6


class OkfError(Exception):
    """Expected, user-facing failure from an OKF operation."""

    exit_code = ExitCode.OPERATIONAL

    def __init__(self, message: str, *, exit_code: ExitCode | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class UsageError(OkfError):
    exit_code = ExitCode.USAGE


class ConfigurationError(OkfError):
    exit_code = ExitCode.CONFIGURATION


class ConflictError(OkfError):
    exit_code = ExitCode.CONFLICT


class ValidationError(OkfError):
    exit_code = ExitCode.VALIDATION


class OperationalError(OkfError):
    exit_code = ExitCode.OPERATIONAL
