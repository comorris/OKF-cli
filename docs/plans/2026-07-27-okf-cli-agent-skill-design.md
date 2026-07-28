# OKF CLI Agent Skill Design

**Date:** 2026-07-27  
**Status:** Approved

## Purpose

Create a global Pi skill named `okf-cli` that teaches agents to manage OKF v0.2 catalogs, bundles, concepts, indexes, and logs exclusively through the portable `okf` CLI. The skill must work from any project and favor deterministic, inspectable operations over direct file mutations.

## Location and structure

The skill is documentation-only and lives at `~/.pi/agent/skills/okf-cli/SKILL.md`. It has no helper scripts because the CLI already provides JSON output, dry runs, validation, path checks, atomic writes, and stable exit codes.

## Deterministic transaction

Every mutation resolves explicit absolute project, bundle, and catalog paths; verifies the CLI; runs a JSON dry run; checks both process exit status and response envelope; applies the exact previewed command; validates changed bundles; and verifies registration when applicable. Agents must stop on unexpected output or nonzero status rather than improvising direct edits.

Catalog resolution prefers a user-supplied path, then configured CLI state, then an existing sibling `okf` catalog. If none is available, the agent asks the user. Existing bundle metadata is reused to preserve idempotency. New metadata uses a predictable title derived from the directory basename and a fixed description template.

## Safety policy

Agents do not directly mutate managed OKF files. They do not automatically use `--force` or suppress index, log, registration, or `.gitignore` behavior. Conflicts require explicit user resolution. Validation failures and warnings are surfaced. Temporary body files may be used as CLI input but must remain outside the bundle and be removed afterward.

## Covered workflows

The skill documents catalog initialization, project bundle initialization, registration, listing, concept creation, index rebuilding, log updates, and validation. It includes an exact Hermes Fitness example and a stable exit-code response policy.
