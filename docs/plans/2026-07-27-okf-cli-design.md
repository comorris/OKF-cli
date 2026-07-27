# Portable OKF CLI and Multi-Project Wiki Design

**Date:** 2026-07-27  
**Status:** Approved  
**OKF target:** v0.2

## Goals

Build a portable, noninteractive Python CLI for managing OKF v0.2 knowledge bundles across multiple projects. The first managed catalog will live at `/Users/comorris/Documents/projects/okf`, and the first project bundle will live at `/Users/comorris/Documents/projects/hermes-fitness/okf`. Project bundles are local agent memory and must be excluded from their containing Git repositories.

The initial CLI scope is deterministic bundle management: initialize and register bundles, list bundles, create concepts, regenerate indexes, append logs, and validate bundles. LLM-driven ingestion, search, visualization, and attested-computation execution are deferred.

## Architecture and storage

The CLI is a standalone Python 3.11+ package at `/Users/comorris/Documents/projects/okf-cli`. It uses a `src/` package layout, `argparse`, PyYAML, and standard-library filesystem APIs. It exposes an `okf` console command and does not use macOS-specific APIs or hardcoded user paths.

The global catalog is itself an OKF bundle:

```text
/Users/comorris/Documents/projects/okf/
├── bundle.md
├── index.md
├── log.md
└── bundles/
    ├── index.md
    └── hermes-fitness.md
```

Files below `bundles/` are conformant `Knowledge Bundle Reference` concepts. Each stores a bundle title, description, and relative `resource` path. The global root index is generated from these reference concepts and links directly to the corresponding external bundle directories.

A newly initialized project bundle is intentionally minimal:

```text
<project>/okf/
├── bundle.md
├── index.md
└── log.md
```

`bundle.md` is a conformant concept with `type: Knowledge Bundle`. New subdirectories are created only when concepts require them. Project bundle initialization idempotently adds `/okf/` to the containing project’s `.gitignore`, unless `--no-gitignore` is passed.

## Discovery and configuration

Catalog lookup uses this precedence:

1. Explicit `--catalog` option.
2. `OKF_CATALOG_ROOT` environment variable.
3. `catalog_root` in `~/.config/okf/config.toml`.
4. Contextual discovery where applicable.

Bundle lookup uses explicit `--bundle` first, then `<git-root>/okf`, then `<cwd>/okf` outside Git. Registry resources are relative paths whenever possible so sibling project layouts can move between macOS and Linux without rewriting machine-specific absolute paths.

## Command surface

```text
okf catalog init
okf bundle init
okf bundle register
okf bundle list
okf concept create
okf index rebuild
okf log add
okf validate
okf config show
```

`catalog init` creates the global catalog. `bundle init` creates a project bundle and registers it by default when a catalog is configured. `bundle register` is idempotent and supports existing bundles. `concept create <concept-id>` maps IDs such as `architecture/system-overview` to bundle-relative Markdown paths. It requires `--type` and accepts optional title, description, tags, status, body text, `--body-file`, and `--generated-by`.

Mutations regenerate affected indexes and append logs by default. `--no-index` and `--no-log` support controlled batch operations. Existing concepts are not overwritten without `--force`. Every mutating command supports `--dry-run`.

## Agent and automation contract

Every command supports `--format text|json`. Commands are noninteractive. Successful data is written to stdout and diagnostics to stderr. JSON mode uses a stable envelope:

```json
{
  "ok": true,
  "command": "bundle.init",
  "data": {},
  "warnings": [],
  "errors": []
}
```

Stable exit codes are:

- `0`: success
- `2`: invalid command usage
- `3`: configuration or path error
- `4`: conflict
- `5`: validation failed
- `6`: filesystem or unexpected operational error

A later agent skill will teach Pi and other compatible harnesses how to choose commands, pass explicit paths, prefer JSON output, use dry runs, and interpret exit codes.

## Indexes, logs, and attribution

Index generation is deterministic: alphabetical ordering, normalized POSIX-style relative links, and descriptions copied from concept frontmatter. Bundle-root `index.md` declares `okf_version: "0.2"`; other indexes contain no frontmatter. The global catalog index links directly to registered bundle directories.

Logs use newest-first ISO `YYYY-MM-DD` date headings. CLI-created content defaults to `generated.by: okf-cli/0.1.0`; callers can supply a different actor with `--generated-by`.

## Validation and safety

Conformance errors include malformed frontmatter, missing or empty `type`, invalid reserved index/log structure, and malformed contract fields when optional OKF families are present. Advisory issues—including broken links, missing descriptions, unknown types, stale concepts, and optional lifecycle/provenance inconsistencies—are warnings. Broken links never make a bundle nonconformant.

Mutation paths are normalized and constrained to their bundle. `..` traversal and symlink escapes are rejected. Writes use temporary sibling files and atomic replacement. Dry runs calculate and report all intended changes without writing.

## Testing and portability

Development follows TDD with pytest and temporary filesystem fixtures. Coverage includes configuration precedence, initialization, idempotent registration, `.gitignore` editing, concept creation, indexes, logs, conformance validation, path security, dry runs, JSON output, and exit codes. End-to-end tests invoke the installed console command in subprocesses. CI targets macOS and Ubuntu on Python 3.11 through 3.13.
