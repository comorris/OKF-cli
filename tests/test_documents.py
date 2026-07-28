from __future__ import annotations

import pytest

from okf_cli.documents import ConceptDocument, parse_concept, render_concept


def test_render_concept_round_trips_frontmatter_and_body() -> None:
    document = ConceptDocument(
        metadata={"type": "Reference", "title": "Café", "tags": ["one", "two"]},
        body="\n# Body\n\nText.\n",
    )

    rendered = render_concept(document)

    assert parse_concept(rendered) == document


def test_render_concept_preserves_unknown_extension_fields() -> None:
    document = ConceptDocument(
        metadata={
            "type": "Reference",
            "x-company": {"owner": "platform", "enabled": True},
        },
        body="",
    )

    parsed = parse_concept(render_concept(document))

    assert parsed.metadata["x-company"] == {"owner": "platform", "enabled": True}


def test_parse_concept_rejects_missing_frontmatter() -> None:
    with pytest.raises(ValueError, match="frontmatter"):
        parse_concept("# No frontmatter\n")


def test_parse_concept_rejects_malformed_yaml() -> None:
    with pytest.raises(ValueError, match="YAML"):
        parse_concept("---\ntype: [broken\n---\n")


def test_parse_concept_rejects_empty_type() -> None:
    with pytest.raises(ValueError, match="type"):
        parse_concept("---\ntype:\n---\n")
