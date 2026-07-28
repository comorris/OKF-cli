# okf-cli

`okf-cli` is a portable, noninteractive Python 3.11+ command-line tool for
managing OKF v0.2 knowledge bundles. It uses only standard filesystem APIs
and PyYAML; paths are supplied explicitly or discovered from the current
project.

## Installation

```bash
pipx install .
uv tool install .

python3.11 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

The editable virtualenv installation is useful for development. The console
command is `okf`.

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
conflict requiring an explicit decision before using `--force`.
