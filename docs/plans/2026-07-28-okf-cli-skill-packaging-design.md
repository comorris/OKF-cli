# OKF CLI Skill Packaging Design

## Goal

Make the `OKF-cli` repository the canonical, installable home of the `okf-cli`
Pi skill while updating its workflow for the provenance-capable `0.2.0`
release.

## Package architecture

The canonical skill will live at `skills/okf-cli/SKILL.md`. Pi discovers
`SKILL.md` files recursively under the conventional `skills/` directory, so
the Python repository does not need a Node `package.json` or a separate package
repository. Users install the skill directly with:

```bash
pi install git:github.com/comorris/OKF-cli
```

The repository copy is authoritative. The existing global skill at
`~/.pi/agent/skills/okf-cli/SKILL.md` will be synchronized from it so current
local invocations receive the same guidance immediately.

## Skill behavior

Setup will require `okf-cli 0.2.0` or newer and verify capabilities rather than
trusting the version string alone. It will check that `concept update` exists,
that provenance options are available on creation and update, and that update
does not expose `--force`. Stale uv installations will receive an explicit
force-reinstallation command instead of falling back to an unverified checkout.

The existing deterministic JSON dry-run, inspection, application, and
validation workflow remains unchanged. The provenance example will initialize
both temporary files before use. Archive ingestion guidance will call the
repository extractor relative to `{baseDir}`, require output outside the bundle,
explain that all JSONL sessions are emitted after message filtering, inspect
`skipped_records`, and remove temporary output. Privacy rules exclude raw
transcripts, credentials, personal health records, and user-specific meal or
workout data from curated concepts. Code and tests outrank documentation,
plans, and conversations; conversations establish rationale, not current
behavior.

## Documentation and validation

The root README will describe skill installation and invocation. Validation
will verify YAML frontmatter, directory/name agreement, referenced repository
files, exact synchronization with the global copy, capability checks against
the installed CLI, archive helper tests, the complete Python test suite, and
Git diff hygiene. An independent read-only review will precede merging and
pushing `main` without force.
