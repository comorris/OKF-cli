from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OKF = ROOT / ".venv" / "bin" / "okf"


def run_okf(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("OKF_CATALOG_ROOT", None)
    return subprocess.run(
        [str(OKF), *args],
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
    )


def test_console_end_to_end_initializes_registers_lists_creates_and_validates(
    tmp_path: Path,
) -> None:
    catalog = tmp_path / "catalog"
    bundle = tmp_path / "project" / "okf"

    result = run_okf(
        "--format",
        "json",
        "catalog",
        "init",
        "--catalog",
        str(catalog),
        "--title",
        "Projects",
        "--description",
        "Project catalog.",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr

    result = run_okf(
        "--format",
        "json",
        "bundle",
        "init",
        "--bundle",
        str(bundle),
        "--catalog",
        str(catalog),
        "--title",
        "Project",
        "--description",
        "Project knowledge.",
        "--no-gitignore",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr

    result = run_okf(
        "--format",
        "json",
        "bundle",
        "list",
        "--catalog",
        str(catalog),
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert "Project" in result.stdout

    result = run_okf(
        "--format",
        "json",
        "concept",
        "create",
        "architecture/overview",
        "--bundle",
        str(bundle),
        "--type",
        "Reference",
        "--title",
        "Overview",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr

    result = run_okf(
        "--format",
        "json",
        "validate",
        "--bundle",
        str(bundle),
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert '"ok": true' in result.stdout


def test_console_output_contains_no_macos_specific_path_assumptions(tmp_path: Path) -> None:
    result = run_okf(
        "--format",
        "json",
        "config",
        "show",
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "/Users/comorris" not in result.stdout + result.stderr
