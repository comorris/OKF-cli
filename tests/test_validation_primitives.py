from __future__ import annotations

from datetime import date
from pathlib import Path

from okf_cli.documents import ConceptDocument
from okf_cli.validation import validate_concept, validate_index, validate_log


def errors(findings: list[object]) -> list[object]:
    return [finding for finding in findings if finding.severity == "error"]


def test_root_index_accepts_only_okf_version_frontmatter() -> None:
    content = "---\nokf_version: \"0.2\"\n---\n# Index\n"

    findings = validate_index(content, root=True, path="index.md")

    assert errors(findings) == []


def test_nested_index_rejects_frontmatter() -> None:
    content = "---\nokf_version: \"0.2\"\n---\n# Nested\n"

    findings = validate_index(content, root=False, path="group/index.md")

    assert any(finding.code == "nested-index-frontmatter" for finding in errors(findings))


def test_log_accepts_iso_date_headings_newest_first() -> None:
    content = "# Directory Update Log\n\n## 2026-07-27\n* **Update**: Newer.\n\n## 2026-07-26\n* **Update**: Older.\n"

    assert errors(validate_log(content, path="log.md")) == []


def test_log_rejects_non_iso_date_heading() -> None:
    content = "# Directory Update Log\n\n## July 27, 2026\n* **Update**: Invalid.\n"

    findings = validate_log(content, path="log.md")

    assert any(finding.code == "invalid-log-date" for finding in errors(findings))


def test_attested_computation_requires_runtime() -> None:
    document = ConceptDocument(metadata={"type": "Attested Computation"}, body="")

    findings = validate_concept(document, path="computation.md")

    assert any(finding.code == "missing-runtime" for finding in errors(findings))


def test_verified_mapping_and_list_are_both_accepted() -> None:
    for verified in (
        {"by": "human:reviewer", "at": "2026-07-27T10:00:00Z"},
        [{"by": "process:check", "at": "2026-07-27T10:00:00Z"}],
    ):
        document = ConceptDocument(
            metadata={"type": "Reference", "verified": verified}, body=""
        )

        assert errors(validate_concept(document, path="concept.md")) == []


def test_broken_markdown_link_is_warning_not_error(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    document = ConceptDocument(
        metadata={"type": "Reference"}, body="See [missing](missing.md).\n"
    )

    findings = validate_concept(
        document,
        path=bundle / "concept.md",
        bundle_root=bundle,
    )

    assert errors(findings) == []
    assert any(finding.code == "broken-link" for finding in findings)


def test_stale_after_on_or_before_today_is_warning() -> None:
    for stale_after in ("2026-07-27", "2026-07-26"):
        document = ConceptDocument(
            metadata={"type": "Reference", "stale_after": stale_after}, body=""
        )

        findings = validate_concept(
            document,
            path="concept.md",
            today=date(2026, 7, 27),
        )

        assert errors(findings) == []
        assert any(finding.code == "stale-concept" for finding in findings)
