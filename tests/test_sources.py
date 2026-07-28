from __future__ import annotations

from pathlib import Path

from okf_cli.sources import load_sources_file, validate_sources_value


def source_errors(findings: list[object]) -> list[object]:
    return [finding for finding in findings if finding.severity == "error"]


def test_load_sources_file_accepts_yaml_list(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(
        "- id: readme\n  resource: ../../README.md\n  last_modified: 2026-07-18\n",
        encoding="utf-8",
    )

    assert load_sources_file(path) == [
        {"id": "readme", "resource": "../../README.md", "last_modified": "2026-07-18"}
    ]


def test_load_sources_file_accepts_json_list(tmp_path: Path) -> None:
    path = tmp_path / "sources.json"
    path.write_text('[{"resource": "https://example.test/spec"}]', encoding="utf-8")

    assert load_sources_file(path) == [{"resource": "https://example.test/spec"}]


def test_load_sources_file_rejects_non_list_root(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text("resource: README.md\n", encoding="utf-8")

    try:
        load_sources_file(path)
    except Exception as exc:
        assert exc.__class__.__name__ == "ConfigurationError"
    else:
        raise AssertionError("expected ConfigurationError")


def test_load_sources_file_requires_resource_per_entry(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text("- id: missing-resource\n", encoding="utf-8")

    try:
        load_sources_file(path)
    except Exception as exc:
        assert exc.__class__.__name__ == "ConfigurationError"
    else:
        raise AssertionError("expected ConfigurationError")


def test_load_sources_file_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(
        "- id: duplicate\n  resource: one.md\n- id: duplicate\n  resource: two.md\n",
        encoding="utf-8",
    )

    try:
        load_sources_file(path)
    except Exception as exc:
        assert exc.__class__.__name__ == "ConfigurationError"
    else:
        raise AssertionError("expected ConfigurationError")


def test_load_sources_file_preserves_unknown_entry_fields(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(
        "- id: readme\n"
        "  resource: README.md\n"
        "  extension: {review: required, rank: 1}\n",
        encoding="utf-8",
    )

    sources = load_sources_file(path)

    assert sources[0]["extension"] == {"review": "required", "rank": 1}


def test_source_validation_rejects_invalid_usage_count() -> None:
    findings = validate_sources_value(
        [{"resource": "README.md", "usage_count": -1}], path="concept.md"
    )

    assert any(finding.code == "invalid-source-usage-count" for finding in source_errors(findings))


def test_source_validation_rejects_invalid_last_modified() -> None:
    findings = validate_sources_value(
        [{"resource": "README.md", "last_modified": "July 18, 2026"}], path="concept.md"
    )

    assert any(finding.code == "invalid-source-last-modified" for finding in source_errors(findings))


def test_source_validation_rejects_invalid_usage_window() -> None:
    findings = validate_sources_value(
        [
            {
                "resource": "README.md",
                "usage_window": {"from": "2026-07-20", "to": "2026-07-18"},
            }
        ],
        path="concept.md",
    )

    assert any(finding.code == "invalid-source-usage-window" for finding in source_errors(findings))


def test_missing_relative_source_is_warning_not_error(tmp_path: Path) -> None:
    findings = validate_sources_value(
        [{"resource": "../missing/README.md"}],
        path=str(tmp_path / "bundle" / "concept.md"),
        bundle_root=tmp_path / "bundle",
    )

    assert source_errors(findings) == []
    assert any(finding.code == "missing-source-resource" for finding in findings)


def test_url_and_scope_descriptor_sources_are_not_filesystem_checked(tmp_path: Path) -> None:
    findings = validate_sources_value(
        [
            {"resource": "https://example.test/spec"},
            {"resource": "scope:current-code"},
            {"resource": "conversation:session.jsonl#member"},
        ],
        path=str(tmp_path / "bundle" / "concept.md"),
        bundle_root=tmp_path / "bundle",
    )

    assert not any(finding.code == "missing-source-resource" for finding in findings)
