from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "okf-cli" / "SKILL.md"


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
