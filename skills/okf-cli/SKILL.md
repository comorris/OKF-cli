---
name: okf-cli
description: Deterministically manages Open Knowledge Format (OKF) v0.2 catalogs, project bundles, concepts, indexes, and logs through the portable okf CLI. Use when creating, registering, validating, or updating OKF knowledge for a project; never mutate managed OKF files directly.
compatibility: "Requires Bash and okf-cli 0.2.0+ on PATH; supports macOS and Linux."
---

# Deterministic OKF CLI Management

Use the `okf` CLI as the exclusive mutation interface for managed OKF v0.2 knowledge. Direct reads are allowed for inspection, but do not create or edit files inside an OKF bundle with generic file-writing tools.

## Required invariants

1. Use explicit absolute `--bundle` and `--catalog` paths in mutations.
2. Use `--format json` for every agent invocation.
3. Preview every mutation with `--dry-run`.
4. Check both the process exit code and JSON `ok` value.
5. Apply exactly the previewed command with only `--dry-run` removed.
6. Validate every changed bundle after applying.
7. Validate and list the catalog after registration changes.
8. Surface warnings and findings; never silently discard them.
9. Do not automatically use `--force`, `--no-index`, `--no-log`, `--no-register`, or `--no-gitignore`.
10. Never infer success from files appearing on disk or from partial stdout.

## Setup check

Before doing anything:

```bash
command -v okf
okf --version
```

Require `okf-cli 0.2.0` or newer. Do not trust the version string alone: inspect the command capabilities before mutating anything.

```bash
okf concept create --help
okf concept update --help
okf concept create --help | grep -F -- '--resource'
okf concept create --help | grep -F -- '--sources-file'
okf concept update --help | grep -F -- '--resource'
okf concept update --help | grep -F -- '--sources-file'
if okf concept update --help | grep -F -- '--force'; then
  printf '%s\n' 'unsupported stale CLI: concept update must not expose --force' >&2
  exit 3
fi
```

Stop and ask the user to install `okf-cli` if it is unavailable, older than
`0.2.0`, or missing any required capability. Do not silently invoke an
unverified checkout or hardcode a machine-specific executable. Supported
installations include:

```bash
pipx install /path/to/okf-cli
uv tool install /path/to/okf-cli
```

For a stale uv tool, explicitly reinstall the intended checkout before
retrying; do not fall back to an unverified global executable:

```bash
uv tool install --force /path/to/okf-cli
```

## Normalize the requested project path

Pi users may prefix paths with `@`. Strip one leading `@`, expand `~`, resolve the path to an absolute path, and verify it is an existing directory. Treat that directory as `PROJECT_ROOT` and use:

```text
BUNDLE_ROOT = <PROJECT_ROOT>/okf
```

Do not accept a file path as a project root. Do not follow a resolved project path outside the location the user named without reporting the resolution.

## Resolve the catalog deterministically

Use the first valid source:

1. A catalog path explicitly supplied by the user.
2. The non-null `catalog_root` returned by:

   ```bash
   okf --format json config show
   ```

3. An existing sibling catalog at `<parent-of-PROJECT_ROOT>/okf` whose `bundle.md` is readable.

If no catalog resolves, ask the user for its path. Do not create a catalog merely because a bundle was requested. Never use the project bundle itself as the global catalog.

## Derive new bundle metadata

If `BUNDLE_ROOT/bundle.md` already exists, read its `title` and `description` and reuse them exactly for idempotent operations.

For a new bundle when the user did not provide metadata:

- `title`: split the project directory basename on hyphens and underscores, then title-case the words.
- `description`: `Project knowledge for the <Title> project.`

Show derived metadata in the dry-run command. User-provided metadata always wins. Let the CLI use its default `generated.by` unless the user explicitly provides an OKF actor.

## Execute a command safely

Run commands in a shell block that preserves stdout, stderr, and the actual exit status:

```bash
stdout_file="$(mktemp)"
stderr_file="$(mktemp)"
set +e
okf --format json <command-and-explicit-options> >"$stdout_file" 2>"$stderr_file"
status=$?
set -e
cat "$stdout_file"
cat "$stderr_file" >&2
printf 'OKF_EXIT_CODE=%s\n' "$status"
rm -f "$stdout_file" "$stderr_file"
```

Inspect the JSON before continuing. A mutation preview is approved for application only when:

- exit status is `0`;
- JSON `ok` is `true`;
- JSON `errors` is empty;
- all reported paths match the requested project, bundle, and catalog;
- the proposed changes match the user’s intent.

Then rerun the exact command with only `--dry-run` removed. Do not combine preview and apply with `&&`; the agent must inspect the preview between them.

## Create or initialize a project bundle

Given `PROJECT_ROOT`, `BUNDLE_ROOT`, `CATALOG_ROOT`, `TITLE`, and `DESCRIPTION`:

### 1. Preview

```bash
okf --format json bundle init \
  --bundle "$BUNDLE_ROOT" \
  --catalog "$CATALOG_ROOT" \
  --title "$TITLE" \
  --description "$DESCRIPTION" \
  --dry-run
```

### 2. Inspect and apply

If the preview passes the safe-execution checks, run the identical command without `--dry-run`.

### 3. Validate and verify registration

```bash
okf --format json validate --bundle "$BUNDLE_ROOT"
okf --format json validate --bundle "$CATALOG_ROOT"
okf --format json bundle list --catalog "$CATALOG_ROOT"
```

Require both validations to exit 0 with `ok: true`. Confirm the list contains one entry whose resolved path equals `BUNDLE_ROOT` and whose title and description match `bundle.md`.

If `PROJECT_ROOT` is inside a Git repository, verify that bundle content is ignored:

```bash
git -C "$PROJECT_ROOT" check-ignore -q "$BUNDLE_ROOT/bundle.md"
```

If this fails, report it. Do not directly edit `.gitignore`; rerun or diagnose `bundle init` instead.

`bundle init` is idempotent. An existing valid bundle may produce no planned writes and still succeed.

## Hermes Fitness example

For a request such as:

```text
Create an OKF bundle for @/Users/comorris/Documents/projects/hermes-fitness/
```

resolve:

```bash
PROJECT_ROOT=/Users/comorris/Documents/projects/hermes-fitness
BUNDLE_ROOT=/Users/comorris/Documents/projects/hermes-fitness/okf
CATALOG_ROOT=/Users/comorris/Documents/projects/okf
TITLE="Hermes Fitness"
DESCRIPTION="Project knowledge for the Hermes Fitness application."
```

If the bundle already exists, read and reuse its current title and description rather than replacing them. Preview `bundle init`, inspect the JSON and status, apply only if needed, then validate the project bundle and catalog and confirm Hermes Fitness appears exactly once in `bundle list`.

## Initialize a catalog

Only initialize a catalog when the user explicitly requests it or approves creation after discovery fails.

```bash
okf --format json catalog init \
  --catalog "$CATALOG_ROOT" \
  --title "$TITLE" \
  --description "$DESCRIPTION" \
  --dry-run
```

Inspect, then apply without `--dry-run`. Finish with:

```bash
okf --format json validate --bundle "$CATALOG_ROOT"
```

## Register an existing bundle

First validate the bundle:

```bash
okf --format json validate --bundle "$BUNDLE_ROOT"
```

If valid, preview and apply registration:

```bash
okf --format json bundle register \
  --bundle "$BUNDLE_ROOT" \
  --catalog "$CATALOG_ROOT" \
  --dry-run
```

After applying, validate the catalog and confirm exactly one matching entry with `bundle list`.

## Create a concept

Concept IDs are bundle-relative paths without `.md`, for example `architecture/system-overview`. Require a non-empty type. Prefer `--body-file` for multiline bodies; create the temporary file outside the bundle and remove it after the command.

```bash
body_file="$(mktemp)"
cat >"$body_file" <<'MARKDOWN'
# Overview

Describe the concept here.
MARKDOWN

okf --format json concept create architecture/system-overview \
  --bundle "$BUNDLE_ROOT" \
  --type Reference \
  --title "System Overview" \
  --description "High-level architecture and component boundaries." \
  --status stable \
  --body-file "$body_file" \
  --dry-run
```

Inspect the preview, apply the exact command without `--dry-run`, remove the temporary file, and validate the bundle.

If the concept already exists, exit code 4 is expected. Do not retry with `--force`. Read the existing concept and use `concept update` for an intentional change. Reserve `--force` for an explicitly approved replacement and warn that it may replace unknown frontmatter fields.

### Provenance options

For synthesized concepts, use `--resource <uri-or-path>` and
`--sources-file <yaml-or-json>`. The sources file must contain a top-level
list; each mapping requires a non-empty `resource` and may include `id`,
`title`, `author`, `usage_count`, `last_modified`, `usage_window`, and
unknown OKF extension fields. IDs must be unique. Relative missing targets are
reported as warnings, not validation errors.

```bash
sources_file="$(mktemp)"
trap 'rm -f "$body_file" "$sources_file"' EXIT
cat >"$sources_file" <<'YAML'
- id: readme
  resource: ../../README.md
  title: Project README
  last_modified: 2026-07-18
YAML

okf --format json concept create architecture/system-overview \
  --bundle "$BUNDLE_ROOT" \
  --type Architecture \
  --resource README.md \
  --sources-file "$sources_file" \
  --body-file "$body_file" \
  --dry-run
```

### Update an existing concept

`concept update` merges only explicitly supplied fields and preserves omitted
metadata, body, sources, and unknown frontmatter extensions. Supplying
`--sources-file` replaces `sources`; supplying `--body` or `--body-file`
replaces the body. There is no `--force` option.

```bash
okf --format json concept update architecture/system-overview \
  --bundle "$BUNDLE_ROOT" \
  --title "System overview" \
  --dry-run
```

Inspect that JSON preview, run the exact command again with only `--dry-run`
removed, then validate the bundle. A meaningful update rebuilds indexes and
adds one `Update` log entry. A no-op reports `updated: false`, writes no files,
and adds no log entry.

## Pi conversation archive extraction

The repository helper streams a Pi ZIP archive without extracting its members.
Invoke it relative to this skill with `{baseDir}/../../scripts/extract_pi_archive.py`.
Always choose an output directory outside the managed bundle; the helper rejects
bundle-contained output and requires the output directory not to exist yet:

```bash
archive_parent="$(mktemp -d)"
archive_output="$archive_parent/sessions"
python3 "{baseDir}/../../scripts/extract_pi_archive.py" \
  --archive /path/to/pi-conversations.zip \
  --bundle "$BUNDLE_ROOT" \
  --out "$archive_output"
```

The output directory contains `inventory.json` and `sessions.jsonl`. All JSONL
sessions are emitted after event filtering to user and assistant text. Inspect
each session's `skipped_records`: malformed, oversized, and non-object records
increment that count. Keep the output as temporary sensitive working data;
select relevant sessions and synthesize only non-personal rationale or history.
Never copy raw transcripts, credentials, personal health records, or
user-specific meal or workout data into curated concepts. Current code and tests remain authoritative; plans and conversations establish rationale, not current behavior. Always remove the output directory after privacy-conscious synthesis,
even when synthesis fails:

```bash
rm -rf "$archive_parent"
```

## Rebuild indexes

Use normal mode for a project bundle and catalog mode for the global catalog:

```bash
okf --format json index rebuild --bundle "$BUNDLE_ROOT" --dry-run
okf --format json index rebuild --bundle "$CATALOG_ROOT" --catalog-mode --dry-run
```

Inspect, apply, and validate the affected bundle. Do not directly edit generated `index.md` files.

## Add a log entry

Kinds are `Initialization`, `Creation`, `Update`, and `Deprecation`.

```bash
okf --format json log add \
  --bundle "$BUNDLE_ROOT" \
  --kind Update \
  --message "Updated the system overview." \
  --dry-run
```

Use `--scope <bundle-relative-directory>` only when the user’s requested log belongs below the root. Inspect, apply, and validate. Do not directly edit `log.md`.

## Read-only inspection

These commands do not require dry runs:

```bash
okf --format json config show
okf --format json bundle list --catalog "$CATALOG_ROOT"
okf --format json validate --bundle "$BUNDLE_ROOT"
```

Directly reading Markdown is allowed when needed to understand existing knowledge or preserve metadata. Direct mutation is not.

## Exit-code policy

- `0`: Continue only if JSON `ok` is also true. Report warnings.
- `2`: Stop; the command invocation is invalid. Correct arguments from `okf <command> --help`, then preview again.
- `3`: Stop; report the configuration or path error. Ask for a path when resolution is ambiguous.
- `4`: Stop; report the conflict. Never add `--force` without explicit user approval.
- `5`: Stop; report every validation finding from `data.findings`. Do not mutate around validation failures.
- `6`: Stop; report the filesystem or operational error. Do not retry with direct file edits.
- Any undocumented code: Stop and report it as an unsupported CLI outcome.

## Completion report

Report:

- resolved project, bundle, and catalog paths;
- whether the mutation was a no-op or which CLI operations were applied;
- validation findings and warnings;
- registration verification;
- Git ignore verification when applicable;
- any action requiring user approval.

Do not claim completion without fresh validation output from the final filesystem state.

## When to use

Use this skill when the user asks to:

- create or initialize an OKF catalog or project bundle;
- register or list knowledge bundles;
- create an OKF concept;
- rebuild OKF indexes;
- append an OKF update log;
- validate an OKF bundle;
- manage project memory or wiki knowledge through `okf-cli`.
