# Hermes Fitness OKF Population Design

**Date:** 2026-07-28  
**Status:** Approved  
**Target:** OKF v0.2

## Goal

Populate `/Users/comorris/Documents/projects/hermes-fitness/okf` with a foundational set of approximately 15–20 curated concepts derived from current code, tests, README documentation, design and planning documents, and archived Pi conversations. Preserve current behavior, durable rationale, and useful project history without copying raw source documents or exposing personal information.

## Approach

Use a hybrid knowledge model:

- Curated current-state concepts for architecture, interfaces, domains, operations, and troubleshooting.
- Individual decision concepts only for major architectural choices.
- Thematic historical summaries for superseded plans and project evolution.
- Conversation history as context and rationale, never as raw transcript or primary proof of current behavior.

Avoid one concept per source document and avoid a single monolithic project-history document.

## Source authority

When sources conflict, use this order:

1. Current code and tests.
2. Current README and operational documentation.
3. Implementation notes and completed plans.
4. Design documents and proposed plans.
5. Conversation history.

Record unresolved discrepancies instead of silently reconciling them. Mark superseded proposal concepts `deprecated`. Mark an open-questions concept `draft`. Use `stable` only for current knowledge corroborated by authoritative sources.

## Privacy boundary

Exclude all personal health data, credentials, tokens, environment values, and user-specific meal or workout records. Retain only software architecture, behavior, decisions, bugs, operational procedures, and non-personal technical lessons.

The archive `/Users/comorris/Documents/projects/hermes-fitness/okf/iphone-fitness-app-pi-conversations.zip` contains 40 JSONL sessions and approximately 284 MB uncompressed. Stream members from ZIP; never fully extract the archive into the bundle. Never place raw transcript content in concepts.

## Knowledge architecture

Create directories only when they receive content:

```text
overview/
architecture/
interfaces/
domains/
operations/
troubleshooting/
decisions/
history/
references/
```

The foundational concept set should cover:

1. Project overview.
2. Privacy and security boundary.
3. System architecture.
4. Data and persistence model.
5. Local-first synchronization model.
6. Backend API surface.
7. Pi/Hermes tools interface.
8. iOS application architecture.
9. Nutrition domain.
10. Recipe domain.
11. Workout domain.
12. Health and body metrics domain.
13. Setup and configuration.
14. Test strategy and commands.
15. Server operations and recovery.
16. Sync/tombstone troubleshooting.
17. Local-first and idempotency decision.
18. Project evolution.
19. Open questions and incomplete work.
20. Source inventory and ingestion policy.

Concepts should cross-link to related concepts. Each concept answers one durable question and does not mirror a source document.

## Provenance

Use OKF `sources` for every synthesized concept. Prefer portable relative paths such as repository files, test files, and documentation. Conversation-derived sources identify both the archive and specific JSONL member. Conversation evidence may support rationale but must not independently establish current implementation behavior.

The source inventory records relative path/member, source category, modification date or session timestamp, size, SHA-256 digest, extraction date, exclusions, and known coverage gaps.

## Source-processing flow

Use a temporary workspace outside the bundle:

1. Inventory source files and archive members with stable identifiers and SHA-256 digests.
2. Classify documentation as current reference, implementation note, design proposal, superseded plan, troubleshooting guide, or example.
3. Use CodeGraph and targeted source/test reads to corroborate current implementation claims.
4. Stream each conversation JSONL member and retain only session metadata, user-stated software goals/constraints, assistant final summaries, explicit decisions, unresolved technical questions, and confirmed debugging outcomes.
5. Discard model settings, thinking events, tool-call payloads, raw command output, repeated context, secrets, personal data, and health/meal/workout records.
6. Process large sessions in bounded chunks and delete temporary extracts after synthesis.
7. Produce candidate claims with source identifiers.
8. Corroborate current claims against higher-authority sources.
9. Create concepts through the CLI, validate each batch, then run a cross-concept deduplication and link review.

## CLI enhancement

Before population, enhance `okf-cli` with:

```text
okf concept create ... --resource <uri-or-path> --sources-file <yaml-or-json>
okf concept update <concept-id> ... [metadata/body options]
```

A sources file contains a top-level list of OKF source mappings. Each entry requires `resource` and may include `id`, `title`, `author`, `usage_count`, `last_modified`, and `usage_window`. Validate unique IDs and supported value shapes. Preserve unknown OKF extension fields.

`concept update` parses the existing concept and merges only explicitly supplied fields. Unspecified metadata and unknown fields remain semantically unchanged. Supplying `--sources-file` replaces `sources`; omitting it preserves current sources. A meaningful update refreshes `generated`; a no-op writes nothing and creates no log entry.

Both create and update retain dry-run support, JSON output, atomic writes, deterministic indexes and logs, path containment, and stable exit codes. Missing relative source targets are warnings, not conformance failures.

## Safety and verification

- Mutate managed bundles only through `okf-cli`.
- Preview every mutation in JSON mode with `--dry-run`.
- Apply the exact previewed command with only `--dry-run` removed.
- Validate after each batch.
- Never use `--force` automatically.
- Scan generated concepts for credential patterns and personal data.
- Review duplicate titles, source coverage, broken links, terminology, and cross-links.
- Require code/test corroboration for stable current-state claims.
- Finish with zero validation errors and explicit review of warnings.

## Testing

CLI tests cover YAML and JSON source files, malformed sources, duplicate IDs, unknown-field preservation, no-op updates, dry-run fidelity, citations, external relative source paths, and create→update→validate integration.

Population verification covers archive streaming without extraction, bounded processing of large members, deterministic inventory digests, privacy exclusions, source coverage, source-authority enforcement, concept count/taxonomy, link integrity, secret scanning, and final OKF validation.
