from __future__ import annotations

import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SKILL = ROOT / "skills" / "okf-cli" / "SKILL.md"
OKF = ROOT / ".venv" / "bin" / "okf"


def _skill_parts() -> tuple[dict[str, object], str]:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    frontmatter, body = text.split("\n---\n", 1)
    metadata = yaml.safe_load(frontmatter.removeprefix("---\n"))
    assert isinstance(metadata, dict)
    return metadata, body


def test_packaged_skill_has_expected_frontmatter() -> None:
    metadata, _ = _skill_parts()

    assert metadata["name"] == "okf-cli"
    assert isinstance(metadata["description"], str)
    assert metadata["description"].strip()


def test_packaged_skill_exists_in_conventional_discovery_path() -> None:
    assert SKILL.is_file()


def test_packaged_skill_archive_helper_reference_resolves() -> None:
    helper = (SKILL.parent / "../../scripts/extract_pi_archive.py").resolve()

    assert helper == ROOT / "scripts" / "extract_pi_archive.py"
    assert helper.is_file()


def test_readme_documents_pi_skill_installation() -> None:
    readme = README.read_text(encoding="utf-8")
    readme_lower = readme.lower()

    assert "pi install git:github.com/comorris/OKF-cli" in readme
    assert "/skill:okf-cli" in readme
    assert "okf-cli 0.2.0" in readme
    assert "installing the skill" in readme_lower
    assert "installing the `okf` executable" in readme_lower


def test_readme_provenance_options_match_cli_help() -> None:
    readme = README.read_text(encoding="utf-8")
    create_help = subprocess.run(
        [str(OKF), "concept", "create", "--help"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    update_help = subprocess.run(
        [str(OKF), "concept", "update", "--help"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    for option in ("--resource", "--sources-file"):
        assert option in readme
        assert option in create_help
        assert option in update_help
    assert "concept update" in readme
    assert "--force" in create_help
    assert "--force" not in update_help


def test_packaged_skill_documents_current_capabilities_and_privacy_rules() -> None:
    _, body = _skill_parts()
    body_lower = body.lower()
    update_section = body.split("## Update an existing concept", 1)[1].split(
        "## Rebuild indexes", 1
    )[0]

    assert "okf-cli 0.2.0" in body
    assert "--resource" in body
    assert "--sources-file" in body
    assert "concept update" in body
    assert "There is no `--force` option." in update_section
    assert "sources_file=\"$(mktemp)\"" in body
    assert "rm -f \"$body_file\" \"$sources_file\"" in body
    assert "{baseDir}/../../scripts/extract_pi_archive.py" in body
    assert "skipped_records" in body
    assert "temporary sensitive working data" in body
    assert "remove the output directory" in body
    assert "current code and tests remain authoritative" in body_lower
    assert "raw transcripts" in body
    assert "credentials" in body
    assert "personal health records" in body
