from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from okf_cli.paths import contained_path, discover_bundle, resolve_concept_path


def test_bundle_discovery_uses_nearest_git_root(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "package"
    nested.mkdir(parents=True)
    subprocess.run(["git", "init", str(project)], check=True, capture_output=True)
    (project / "okf").mkdir()

    assert discover_bundle(nested) == project / "okf"


def test_bundle_discovery_uses_cwd_without_git(tmp_path: Path) -> None:
    cwd = tmp_path / "not-a-repository"
    cwd.mkdir()

    assert discover_bundle(cwd) == cwd / "okf"


def test_resolve_concept_path_rejects_parent_traversal(tmp_path: Path) -> None:
    bundle = tmp_path / "okf"
    bundle.mkdir()

    with pytest.raises(ValueError):
        resolve_concept_path(bundle, "architecture/../secret")


def test_resolve_mutation_rejects_symlink_escape(tmp_path: Path) -> None:
    bundle = tmp_path / "okf"
    outside = tmp_path / "outside"
    bundle.mkdir()
    outside.mkdir()
    link = bundle / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("platform cannot create directory symlinks")

    with pytest.raises(ValueError):
        contained_path(bundle, "linked/secret.md")
