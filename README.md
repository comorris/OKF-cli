# okf-cli

`okf-cli` is a portable, noninteractive Python 3.11+ command-line tool for
managing OKF v0.2 knowledge bundles. It uses only standard filesystem APIs
and PyYAML; paths are supplied explicitly or discovered from the current
project.

## What's new in 0.2.0

The `okf-provenance-population` release adds the workflow needed to build and
maintain curated, evidence-backed bundles:

- `concept create` accepts a primary `--resource` and structured provenance
  through `--sources-file`.
- `concept update` safely patches existing concepts while preserving omitted
  metadata, body content, sources, and extension fields.
- Source validation checks OKF metadata and reports missing relative resources
  as warnings rather than conformance errors.
- `scripts/extract_pi_archive.py` streams Pi conversation text from ZIP
  archives with bounded per-record memory use.
- Package version and the default `generated.by` actor now share one version
  source, so installed capabilities are distinguishable as `okf-cli 0.2.0`.

This functionality was developed for the Hermes Fitness knowledge population:
a privacy-preserving, thematic synthesis of current code, tests, documentation,
plans, and conversation history. Current code and tests remain authoritative;
conversation archives provide rationale and history rather than proof of
current behavior. See [CHANGELOG.md](CHANGELOG.md) for the complete release
summary.

## Installation

```bash
pipx install .
uv tool install .

python3.11 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

The editable virtualenv installation is useful for development. The console
command is `okf`.

To replace an older global uv installation and verify that the provenance
commands are available:

```bash
uv tool install --force .
okf --version                         # okf-cli 0.2.0
okf concept update --help             # includes --resource and --sources-file
```

## Commands

Commands write successful results to stdout and diagnostics to stderr. They
never prompt for input. Add `--format json` before the command (or on a leaf
command) for the stable JSON envelope with `ok`, `command`, `data`,
`warnings`, and `errors`.

```bash
# Configuration
okf config show
okf --format json config show

# Catalog
okf catalog init --catalog ./okf --title "Projects" --description "Project catalog."
okf --format json catalog init --catalog ./okf --title "Projects" --description "Project catalog."

# Project bundles
okf bundle init --bundle ./okf --catalog ../okf --title "Project" --description "Project knowledge."
okf --format json bundle init --bundle ./okf --catalog ../okf --title "Project" --description "Project knowledge."
okf bundle register --bundle ./okf --catalog ../okf
okf --format json bundle register --bundle ./okf --catalog ../okf
okf bundle list --catalog ../okf
okf --format json bundle list --catalog ../okf

# Concepts
okf concept create architecture/overview --bundle ./okf --type Reference --title "Overview"
okf --format json concept create architecture/overview --bundle ./okf --type Reference --title "Overview"
okf --format json concept create architecture/overview \
  --bundle ./okf --type Reference --resource README.md \
  --sources-file ./sources.yaml --body-file ./overview.md --dry-run
okf --format json concept update architecture/overview \
  --bundle ./okf --title "Updated overview" --dry-run

# Indexes and logs
okf index rebuild --bundle ./okf
okf --format json index rebuild --bundle ./okf
okf log add --bundle ./okf --kind Update --message "Updated overview."
okf --format json log add --bundle ./okf --kind Update --message "Updated overview."

# Validation
okf validate --bundle ./okf
okf --format json validate --bundle ./okf
```

`bundle init` discovers `<git-root>/okf` when `--bundle` is omitted, or uses
`<cwd>/okf` outside Git. Concept IDs are bundle-relative paths without the
`.md` suffix. Use `--body` or UTF-8 `--body-file`, but not both. Mutations
support `--dry-run`; concept creation also supports `--force`, `--no-index`,
and `--no-log`. Bundle initialization adds `/okf/` to the containing
project's `.gitignore` unless `--no-gitignore` is passed.

### Concept provenance and updates

Creation accepts an optional `--resource` and a `--sources-file`. The source
file is YAML or JSON with a top-level list; every entry requires `resource` and
may include `id`, `title`, `author`, `usage_count`, `last_modified`,
`usage_window: {from, to}`, and OKF extension fields. Source IDs are unique.
Relative source paths are checked during validation; missing paths are warnings,
not conformance errors. Unknown source fields are retained.

`concept update` requires an existing concept and merges only options supplied
on the command line. Omitted metadata, sources, body, and unknown frontmatter
fields are preserved. Supplying `--sources-file` replaces `sources`; supplying
`--body` or `--body-file` replaces the body. A no-op writes no files and adds
no log entry. Meaningful updates atomically write the concept, rebuild indexes,
and append one `Update` log entry unless `--no-index` or `--no-log` is passed.
Use `concept update` for changes instead of replacing an existing concept with
`concept create --force`.

## Pi conversation archive extraction

The optional helper script inventories and streams an archive without
extracting ZIP members, using a configurable per-record read bound:

```bash
python scripts/extract_pi_archive.py \
  --archive /path/to/pi-conversations.zip \
  --bundle /path/to/project/okf \
  --out /tmp/project-sessions
```

The output path is a new directory containing `inventory.json` and
`sessions.jsonl`. Every JSONL session in the archive is emitted after events are
filtered to user and assistant text; `--bundle` verifies the project environment
and ensures the output remains outside the managed bundle. Oversized, malformed,
or non-object records are skipped and counted in each session's
`skipped_records` field. Member ordering is deterministic.

Treat the output directory as temporary sensitive working data. Select only
relevant sessions, synthesize only non-personal rationale or history into
concepts, attach source provenance, validate the bundle, and remove the output
directory when finished.

## Configuration and portability

Catalog resolution precedence is:

1. `--catalog` on the command.
2. `OKF_CATALOG_ROOT`.
3. `catalog_root` in `$XDG_CONFIG_HOME/okf/config.toml`.
4. `~/.config/okf/config.toml` when `XDG_CONFIG_HOME` is unset.

The configuration file is TOML:

```toml
catalog_root = "/path/to/okf"
```

Use explicit `--catalog` and `--bundle` paths in automation. The CLI does not
assume `/Users/...`, macOS APIs, or a particular home directory, and works on
macOS and Linux.

## Exit codes

| Code | Meaning |
| ---: | --- |
| 0 | Success, including warning-only validation |
| 2 | Invalid command usage |
| 3 | Configuration or path error |
| 4 | Conflict with existing content |
| 5 | Bundle validation failed |
| 6 | Filesystem or unexpected operational error |

Validation findings are deterministic and sorted. Broken links and stale
concepts are warnings; malformed frontmatter, missing `type`, invalid
reserved documents, and malformed optional contract fields are errors.

## Agent invocation

Agents should use explicit paths, prefer `--format json`, and preview
mutations with `--dry-run` before applying them. Check the process exit code;
do not infer success from partial output. Treat exit code 5 as a nonconformant
bundle requiring inspection of `data.findings`, and treat exit code 4 as a
conflict requiring an explicit decision before using `--force`. For synthesized
concepts, pass provenance through `--sources-file`; for existing concepts use
`concept update`, preview it, apply the exact command without `--dry-run`, and
validate afterward. Report warning-only missing source paths and no-op updates.
