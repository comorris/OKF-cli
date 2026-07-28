from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .errors import ConfigurationError


@dataclass(frozen=True)
class ResolvedCatalog:
    path: Path | None
    source: str


def _expand_path(value: str, home: Path) -> Path:
    if value == "~":
        return home
    if value.startswith("~/"):
        return home / value[2:]
    return Path(value).expanduser()


def _config_path(environ: Mapping[str, str], home: Path) -> Path:
    xdg_home = environ.get("XDG_CONFIG_HOME")
    if xdg_home:
        return _expand_path(xdg_home, home) / "okf" / "config.toml"
    return home / ".config" / "okf" / "config.toml"


def _configured_catalog(config_path: Path, home: Path) -> Path | None:
    if not config_path.is_file():
        return None
    try:
        values = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"could not read config file {config_path}: {exc}") from exc
    value = values.get("catalog_root")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"catalog_root must be a non-empty string in {config_path}")
    return _expand_path(value, home)


def resolve_catalog(
    explicit: Path | None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> ResolvedCatalog:
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    if explicit is not None:
        return ResolvedCatalog(Path(explicit), "cli")

    environment_value = environ.get("OKF_CATALOG_ROOT")
    if environment_value:
        return ResolvedCatalog(_expand_path(environment_value, home), "environment")

    config_path = _config_path(environ, home)
    configured = _configured_catalog(config_path, home)
    if configured is not None:
        return ResolvedCatalog(configured, "config")

    return ResolvedCatalog(None, "unset")


def config_report(
    explicit: Path | None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> dict[str, str | None]:
    resolved = resolve_catalog(explicit, environ, home)
    return {
        "catalog_root": str(resolved.path) if resolved.path is not None else None,
        "source": resolved.source,
    }
