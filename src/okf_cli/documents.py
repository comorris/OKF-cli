from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


class DocumentError(ValueError):
    """A Markdown document does not have a valid OKF frontmatter block."""


class _FrontmatterLoader(yaml.SafeLoader):
    pass


# PyYAML otherwise turns ISO dates and timestamps into datetime objects. Keeping
# them as strings makes frontmatter round-tripping lossless and lets validation
# apply the OKF-specific date rules explicitly.
_FrontmatterLoader.yaml_implicit_resolvers = {
    key: [resolver for resolver in resolvers if resolver[0] != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


@dataclass(frozen=True)
class ConceptDocument:
    metadata: dict[str, Any]
    body: str


def _lines(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = _lines(text)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise DocumentError("document is missing YAML frontmatter")

    closing_index = next(
        (
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.rstrip("\r\n") == "---"
        ),
        None,
    )
    if closing_index is None:
        raise DocumentError("frontmatter has no closing delimiter")

    source = "".join(lines[1:closing_index])
    try:
        metadata = yaml.load(source, Loader=_FrontmatterLoader)
    except yaml.YAMLError as exc:
        raise DocumentError(f"malformed YAML frontmatter: {exc}") from exc
    if not isinstance(metadata, dict):
        raise DocumentError("frontmatter must contain a YAML mapping")
    body = "".join(lines[closing_index + 1 :])
    return dict(metadata), body


def parse_concept(text: str) -> ConceptDocument:
    metadata, body = parse_frontmatter(text)
    concept_type = metadata.get("type")
    if not isinstance(concept_type, str) or not concept_type.strip():
        raise DocumentError("frontmatter type must be a non-empty string")
    return ConceptDocument(metadata=metadata, body=body)


def render_concept(document: ConceptDocument) -> str:
    source = yaml.safe_dump(
        document.metadata,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip("\n")
    return f"---\n{source}\n---\n{document.body}"
