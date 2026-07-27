# Portable OKF CLI Implementation Plan

> **REQUIRED SUB-SKILL:** Use the executing-plans skill to implement this plan task-by-task.

**Goal:** Build a portable Python CLI that manages OKF v0.2 catalogs and project bundles, then use it to scaffold the global catalog and Hermes Fitness bundle.

**Architecture:** Keep OKF parsing, filesystem safety, discovery, indexing, and services independent from the `argparse` adapter. Model the global registry as conformant `Knowledge Bundle Reference` concepts, generate deterministic indexes, and route every mutation through a dry-run-aware atomic filesystem abstraction.

**Tech Stack:** Python 3.11+, `argparse`, `pathlib`, `tomllib`, PyYAML, pytest, setuptools, GitHub Actions.

**Authoritative references:**
- OKF v0.2: <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>
- Approved design: `docs/plans/2026-07-27-okf-cli-design.md`

**TDD constraint:** Implement only the tests listed in each task. Do not add extra tests without revising this plan and receiving approval.

---

## Phase 1: Package and core contracts

### Task 1: Package skeleton, CLI dispatcher, and output contract

**TDD scenario:** New feature — full TDD cycle.

**Files:**
- Create: `pyproject.toml`
- Create: `src/okf_cli/__init__.py`
- Create: `src/okf_cli/__main__.py`
- Create: `src/okf_cli/cli.py`
- Create: `src/okf_cli/errors.py`
- Create: `src/okf_cli/output.py`
- Create: `tests/test_cli_contract.py`

**Authorized tests:**
1. `test_version_from_console_command`: `okf --version` prints `okf-cli 0.1.0` and exits 0.
2. `test_missing_command_is_usage_error`: no subcommand exits 2 without a traceback.
3. `test_json_success_envelope`: a stubbed `config show --format json` result has exactly `ok`, `command`, `data`, `warnings`, and `errors`.
4. `test_domain_error_uses_stable_exit_code`: raising an `OkfError` subclass returns its documented exit code and no traceback.
5. `test_unexpected_error_returns_operational_exit`: unexpected exceptions exit 6 and are concise unless a future debug mode is added.

**Step 1: Write the failing tests**

Use `pytest` with `capsys` and direct calls to `main([...])`. Patch a temporary command handler for the envelope tests rather than implementing domain behavior early.

```python
def test_json_success_envelope(capsys):
    code = main(["--format", "json", "config", "show"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert set(payload) == {"ok", "command", "data", "warnings", "errors"}
```

**Step 2: Run the tests and verify RED**

Run:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest tests/test_cli_contract.py -v
```

Expected: collection/import failure because `okf_cli` does not exist.

**Step 3: Implement the package and minimal dispatcher**

Use setuptools `src` discovery and this console entry point:

```toml
[project.scripts]
okf = "okf_cli.cli:entrypoint"
```

Define `ExitCode` values 0, 2, 3, 4, 5, and 6. `main(argv)` returns an integer; `entrypoint()` raises `SystemExit(main())`. Centralize rendering in:

```python
@dataclass(frozen=True)
class CommandResult:
    command: str
    data: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
```

Do not let domain modules print directly.

**Step 4: Run tests and verify GREEN**

Run: `.venv/bin/pytest tests/test_cli_contract.py -v`  
Expected: 5 passed.

**Step 5: Commit**

```bash
git add pyproject.toml src tests/test_cli_contract.py
git commit -m "feat: establish OKF CLI contracts"
```

---

### Task 2: Configuration, path discovery, and safe filesystem abstraction

**TDD scenario:** New feature — full TDD cycle.

**Files:**
- Create: `src/okf_cli/config.py`
- Create: `src/okf_cli/paths.py`
- Create: `src/okf_cli/filesystem.py`
- Create: `tests/test_config.py`
- Create: `tests/test_paths.py`
- Create: `tests/test_filesystem.py`
- Modify: `src/okf_cli/cli.py`

**Authorized tests:**
1. `test_catalog_cli_option_wins_over_everything`.
2. `test_catalog_environment_wins_over_config_file`.
3. `test_catalog_uses_xdg_config_home`.
4. `test_catalog_defaults_to_home_dot_config`.
5. `test_config_show_reports_value_and_source`.
6. `test_bundle_discovery_uses_nearest_git_root`.
7. `test_bundle_discovery_uses_cwd_without_git`.
8. `test_resolve_concept_path_rejects_parent_traversal`.
9. `test_resolve_mutation_rejects_symlink_escape`.
10. `test_atomic_write_replaces_file_without_partial_content`.
11. `test_dry_run_records_write_without_touching_disk`.

**Step 1: Write the failing tests**

Use `monkeypatch` for `HOME`, `XDG_CONFIG_HOME`, and `OKF_CATALOG_ROOT`. Use temporary directories and a real `git init` for nearest-root discovery. Skip the symlink test only if the platform cannot create symlinks; macOS and Ubuntu runners support them.

**Step 2: Run the tests and verify RED**

Run: `.venv/bin/pytest tests/test_config.py tests/test_paths.py tests/test_filesystem.py -v`  
Expected: import failures for the new modules.

**Step 3: Implement minimal discovery and filesystem APIs**

Required interfaces:

```python
@dataclass(frozen=True)
class ResolvedCatalog:
    path: Path | None
    source: str  # cli | environment | config | unset


def resolve_catalog(explicit: Path | None, environ: Mapping[str, str], home: Path) -> ResolvedCatalog: ...
def discover_bundle(cwd: Path) -> Path: ...
def contained_path(root: Path, relative: str, *, suffix: str = "") -> Path: ...

class FileSystem:
    def __init__(self, dry_run: bool = False): ...
    def write_text(self, path: Path, content: str) -> None: ...
    @property
    def changes(self) -> tuple[PlannedChange, ...]: ...
```

Read TOML with `tomllib`. For writes, create a temporary sibling using `tempfile.NamedTemporaryFile(delete=False, dir=path.parent)`, flush, `os.fsync`, then `os.replace`. Resolve existing parent directories and reject mutations whose real target ancestry leaves the real bundle root.

**Step 4: Run tests and verify GREEN**

Run: `.venv/bin/pytest tests/test_config.py tests/test_paths.py tests/test_filesystem.py -v`  
Expected: 11 passed.

**Step 5: Commit**

```bash
git add src/okf_cli tests/test_config.py tests/test_paths.py tests/test_filesystem.py
git commit -m "feat: add portable discovery and safe writes"
```

---

### Task 3: OKF document parsing, rendering, and conformance primitives

**TDD scenario:** New feature — full TDD cycle.

**Files:**
- Create: `src/okf_cli/documents.py`
- Create: `src/okf_cli/validation.py`
- Create: `tests/test_documents.py`
- Create: `tests/test_validation_primitives.py`

**Authorized tests:**
1. `test_render_concept_round_trips_frontmatter_and_body`.
2. `test_render_concept_preserves_unknown_extension_fields`.
3. `test_parse_concept_rejects_missing_frontmatter`.
4. `test_parse_concept_rejects_malformed_yaml`.
5. `test_parse_concept_rejects_empty_type`.
6. `test_root_index_accepts_only_okf_version_frontmatter`.
7. `test_nested_index_rejects_frontmatter`.
8. `test_log_accepts_iso_date_headings_newest_first`.
9. `test_log_rejects_non_iso_date_heading`.
10. `test_attested_computation_requires_runtime`.
11. `test_verified_mapping_and_list_are_both_accepted`.
12. `test_broken_markdown_link_is_warning_not_error`.
13. `test_stale_after_on_or_before_today_is_warning`.

**Step 1: Write the failing tests**

Fixtures must use only OKF rules in SPEC.md. Do not invent a closed registry of allowed `type` values; producer-defined types remain valid.

**Step 2: Run the tests and verify RED**

Run: `.venv/bin/pytest tests/test_documents.py tests/test_validation_primitives.py -v`  
Expected: import failures.

**Step 3: Implement parsing and findings**

Use `yaml.safe_load`/`yaml.safe_dump(sort_keys=False, allow_unicode=True)`. Preserve unknown mapping keys and require frontmatter delimiters on their own lines. Define:

```python
@dataclass(frozen=True)
class ConceptDocument:
    metadata: dict[str, object]
    body: str

@dataclass(frozen=True)
class Finding:
    severity: Literal["error", "warning"]
    code: str
    path: str
    message: str
```

Validation must apply strict conformance rules to concepts and reserved files while treating broken links and staleness as warnings. Accept bare and list-shaped `verified` values.

**Step 4: Run tests and verify GREEN**

Run: `.venv/bin/pytest tests/test_documents.py tests/test_validation_primitives.py -v`  
Expected: 13 passed.

**Step 5: Commit**

```bash
git add src/okf_cli/documents.py src/okf_cli/validation.py tests/test_documents.py tests/test_validation_primitives.py
git commit -m "feat: parse and validate OKF documents"
```

---

## Phase 2: Deterministic bundle operations

### Task 4: Deterministic indexes and chronological logs

**TDD scenario:** New feature — full TDD cycle.

**Files:**
- Create: `src/okf_cli/indexes.py`
- Create: `src/okf_cli/logs.py`
- Create: `tests/test_indexes.py`
- Create: `tests/test_logs.py`

**Authorized tests:**
1. `test_bundle_root_index_declares_okf_version`.
2. `test_bundle_root_index_lists_bundle_metadata_and_child_groups`.
3. `test_nested_index_has_no_frontmatter`.
4. `test_index_entries_are_sorted_and_include_descriptions`.
5. `test_index_excludes_reserved_files`.
6. `test_catalog_root_index_links_directly_to_registered_bundle_resources`.
7. `test_rebuilding_indexes_twice_is_byte_identical`.
8. `test_append_log_creates_valid_root_log`.
9. `test_append_log_places_newer_date_first`.
10. `test_append_log_groups_entries_on_same_date`.
11. `test_append_log_rejects_invalid_kind_or_scope_path`.

**Step 1: Write failing tests**

Create fixture concepts using `render_concept`; do not hand-roll parser assumptions in the tests. Assert complete expected Markdown for one root, one nested index, and one log.

**Step 2: Run tests and verify RED**

Run: `.venv/bin/pytest tests/test_indexes.py tests/test_logs.py -v`  
Expected: import failures.

**Step 3: Implement generators**

Required behavior:

```python
def rebuild_indexes(bundle_root: Path, fs: FileSystem, *, catalog: bool = False) -> list[Path]: ...
def append_log(scope: Path, kind: str, message: str, *, date: datetime.date, fs: FileSystem) -> Path: ...
```

Walk directories in stable case-folded name order. Root index gets `okf_version: "0.2"`; nested indexes do not. For catalog references, resolve `resource` relative to the reference concept and emit a normalized link relative to the catalog root. Escape Markdown link text and normalize paths to `/` separators.

**Step 4: Run tests and verify GREEN**

Run: `.venv/bin/pytest tests/test_indexes.py tests/test_logs.py -v`  
Expected: 11 passed.

**Step 5: Commit**

```bash
git add src/okf_cli/indexes.py src/okf_cli/logs.py tests/test_indexes.py tests/test_logs.py
git commit -m "feat: generate OKF indexes and logs"
```

---

### Task 5: Catalog and bundle initialization, registration, and listing

**TDD scenario:** New feature — full TDD cycle.

**Files:**
- Create: `src/okf_cli/catalog.py`
- Create: `src/okf_cli/bundles.py`
- Create: `tests/test_catalog.py`
- Create: `tests/test_bundles.py`
- Modify: `src/okf_cli/cli.py`

**Authorized tests:**
1. `test_catalog_init_creates_minimal_conformant_tree`.
2. `test_catalog_init_is_idempotent`.
3. `test_bundle_init_creates_minimal_conformant_tree`.
4. `test_bundle_init_adds_root_okf_rule_to_gitignore`.
5. `test_bundle_init_does_not_duplicate_gitignore_rule`.
6. `test_bundle_init_can_skip_gitignore`.
7. `test_bundle_init_registers_by_default_when_catalog_resolves`.
8. `test_bundle_init_can_skip_registration`.
9. `test_register_writes_relative_resource_when_possible`.
10. `test_register_same_bundle_twice_does_not_duplicate_reference`.
11. `test_register_rejects_missing_or_invalid_bundle_metadata`.
12. `test_bundle_list_is_sorted_and_returns_title_description_and_path`.
13. `test_bundle_init_dry_run_reports_changes_and_writes_nothing`.
14. `test_catalog_and_bundle_commands_emit_json_contract`.

**Step 1: Write failing service and CLI tests**

Call service functions for filesystem detail and `main([...])` for one JSON path per command family. Freeze the clock or pass dates explicitly so generated content is deterministic.

**Step 2: Run tests and verify RED**

Run: `.venv/bin/pytest tests/test_catalog.py tests/test_bundles.py -v`  
Expected: import failures or unrecognized subcommands.

**Step 3: Implement services and adapters**

Create `bundle.md`, `index.md`, and `log.md` with `status: stable` and `generated.by`. Catalog init also creates `bundles/index.md`. Registration creates `bundles/<slug>.md` with `type: Knowledge Bundle Reference`, copies title/description, and stores a resource relative to the reference document’s directory. Slugs must be lowercase kebab-case and collision-safe.

Idempotency means rerunning with equivalent metadata produces no duplicate entries and no meaningless log entry. Do not overwrite conflicting metadata without an explicit future update command.

**Step 4: Run tests and verify GREEN**

Run: `.venv/bin/pytest tests/test_catalog.py tests/test_bundles.py -v`  
Expected: 14 passed.

**Step 5: Commit**

```bash
git add src/okf_cli/cli.py src/okf_cli/catalog.py src/okf_cli/bundles.py tests/test_catalog.py tests/test_bundles.py
git commit -m "feat: initialize and register OKF bundles"
```

---

### Task 6: Concept creation and explicit log command

**TDD scenario:** New feature — full TDD cycle.

**Files:**
- Create: `src/okf_cli/concepts.py`
- Create: `tests/test_concepts.py`
- Create: `tests/test_log_command.py`
- Modify: `src/okf_cli/cli.py`

**Authorized tests:**
1. `test_concept_create_maps_nested_id_to_markdown_path`.
2. `test_concept_create_writes_required_and_optional_metadata`.
3. `test_concept_create_accepts_body_text`.
4. `test_concept_create_accepts_utf8_body_file`.
5. `test_body_and_body_file_are_mutually_exclusive_usage_error`.
6. `test_concept_create_rejects_reserved_id`.
7. `test_concept_create_rejects_absolute_parent_and_symlink_escape`.
8. `test_concept_create_conflicts_without_force`.
9. `test_concept_create_force_replaces_atomically`.
10. `test_concept_create_rebuilds_indexes_and_appends_log_by_default`.
11. `test_concept_create_can_skip_index_and_log`.
12. `test_concept_create_dry_run_reports_all_cascading_changes`.
13. `test_log_add_targets_root_or_valid_nested_scope`.
14. `test_concept_and_log_commands_emit_json_contract`.

**Step 1: Write failing tests**

Use concept IDs without `.md`; explicitly test normalization rejection rather than silently fixing ambiguous IDs. Verify `tags` become a YAML list, `generated.at` is UTC ISO 8601, and default actor is `okf-cli/0.1.0`.

**Step 2: Run tests and verify RED**

Run: `.venv/bin/pytest tests/test_concepts.py tests/test_log_command.py -v`  
Expected: import failures or unrecognized subcommands.

**Step 3: Implement concept and log adapters**

Required service shape:

```python
def create_concept(
    bundle_root: Path,
    concept_id: str,
    *,
    concept_type: str,
    title: str | None,
    description: str | None,
    tags: Sequence[str],
    status: str | None,
    body: str,
    generated_by: str,
    force: bool,
    rebuild: bool,
    log_change: bool,
    fs: FileSystem,
) -> OperationResult: ...
```

Validate actor convention, status values, concept ID segments, and body-file decoding before any mutation. Calculate all writes through the same `FileSystem` so dry-run output includes concept, index, and log changes.

**Step 4: Run tests and verify GREEN**

Run: `.venv/bin/pytest tests/test_concepts.py tests/test_log_command.py -v`  
Expected: 14 passed.

**Step 5: Commit**

```bash
git add src/okf_cli/cli.py src/okf_cli/concepts.py tests/test_concepts.py tests/test_log_command.py
git commit -m "feat: create and log OKF concepts"
```

---

## Phase 3: Validation command, documentation, and real scaffolding

### Task 7: Bundle-wide validation, integration tests, docs, and CI

**TDD scenario:** Modifying tested code — run existing tests first, then full TDD for new integration behavior.

**Files:**
- Create: `tests/test_validate_command.py`
- Create: `tests/test_end_to_end.py`
- Create: `README.md`
- Create: `.github/workflows/ci.yml`
- Modify: `src/okf_cli/validation.py`
- Modify: `src/okf_cli/cli.py`
- Modify: `pyproject.toml`

**Authorized tests:**
1. `test_validate_conformant_bundle_exits_zero`.
2. `test_validate_invalid_bundle_exits_five`.
3. `test_validate_warning_only_bundle_exits_zero`.
4. `test_validate_json_contains_sorted_findings`.
5. `test_validate_missing_bundle_is_path_error`.
6. `test_index_rebuild_command_rebuilds_all_indexes`.
7. `test_config_show_text_and_json_include_catalog_source`.
8. `test_console_end_to_end_initializes_registers_lists_creates_and_validates`.
9. `test_console_output_contains_no_macos_specific_path_assumptions`.

**Step 1: Run the current suite as a baseline**

Run: `.venv/bin/pytest -v`  
Expected: all Task 1–6 tests pass.

**Step 2: Write failing validation and end-to-end tests**

Invoke `.venv/bin/okf` with `subprocess.run(..., text=True, capture_output=True)`. Build the entire catalog/project scenario under `tmp_path`; never rely on `/Users/...` in tests.

**Step 3: Run targeted tests and verify RED**

Run: `.venv/bin/pytest tests/test_validate_command.py tests/test_end_to_end.py -v`  
Expected: failures for missing command wiring or recursive validation.

**Step 4: Implement recursive validation and final command wiring**

Walk all `.md` files in deterministic order, classify reserved documents by filename and location, parse Markdown links, aggregate findings, and raise validation exit 5 only when at least one error exists. Wire `index rebuild` and final `config show` behavior.

**Step 5: Add user documentation and CI**

README must document:
- Python 3.11+ support.
- `pipx install .`, `uv tool install .`, and editable virtualenv installation.
- Every command with text and JSON examples.
- configuration precedence and environment variable.
- exit codes, dry runs, and noninteractive guarantees.
- macOS and Linux notes.
- how an agent should invoke commands safely.

CI matrix:

```yaml
os: [ubuntu-latest, macos-latest]
python-version: ["3.11", "3.12", "3.13"]
```

Run package build, pytest, and `okf --version` in each matrix cell.

**Step 6: Run all verification**

```bash
.venv/bin/pytest -v
.venv/bin/python -m build
.venv/bin/pip install --force-reinstall dist/*.whl
.venv/bin/okf --version
```

Expected: all tests pass, wheel and sdist build, installed command prints version.

**Step 7: Commit**

```bash
git add README.md .github pyproject.toml src/okf_cli tests/test_validate_command.py tests/test_end_to_end.py
git commit -m "feat: complete portable OKF management CLI"
```

---

### Task 8: Scaffold the requested catalog and Hermes Fitness bundle

**TDD scenario:** Trivial deployment/configuration task — use the fully tested CLI; do not add tests.

**Files:**
- Create: `/Users/comorris/Documents/projects/okf/bundle.md`
- Create: `/Users/comorris/Documents/projects/okf/index.md`
- Create: `/Users/comorris/Documents/projects/okf/log.md`
- Create: `/Users/comorris/Documents/projects/okf/bundles/index.md`
- Create: `/Users/comorris/Documents/projects/okf/bundles/hermes-fitness.md`
- Create: `/Users/comorris/Documents/projects/hermes-fitness/okf/bundle.md`
- Create: `/Users/comorris/Documents/projects/hermes-fitness/okf/index.md`
- Create: `/Users/comorris/Documents/projects/hermes-fitness/okf/log.md`
- Modify: `/Users/comorris/Documents/projects/hermes-fitness/.gitignore`

**Step 1: Preview catalog initialization**

```bash
.venv/bin/okf --format json catalog init \
  --catalog /Users/comorris/Documents/projects/okf \
  --title "Projects Knowledge Catalog" \
  --description "Index of OKF knowledge bundles for local projects." \
  --dry-run
```

Expected: `ok: true`; planned writes reported; no catalog directory created.

**Step 2: Initialize the catalog**

Run the same command without `--dry-run`.  
Expected: minimal conformant catalog tree created.

**Step 3: Preview Hermes Fitness initialization**

```bash
.venv/bin/okf --format json bundle init \
  --bundle /Users/comorris/Documents/projects/hermes-fitness/okf \
  --catalog /Users/comorris/Documents/projects/okf \
  --title "Hermes Fitness" \
  --description "Project knowledge for the Hermes Fitness application." \
  --dry-run
```

Expected: planned project files, `.gitignore` update, catalog reference, indexes, and logs; no writes.

**Step 4: Initialize and register Hermes Fitness**

Run the same command without `--dry-run`.  
Expected: bundle created, `/okf/` appears exactly once in `.gitignore`, and catalog reference uses a relative resource.

**Step 5: Validate and inspect**

```bash
.venv/bin/okf --format json validate --bundle /Users/comorris/Documents/projects/okf
.venv/bin/okf --format json validate --bundle /Users/comorris/Documents/projects/hermes-fitness/okf
.venv/bin/okf --format json bundle list --catalog /Users/comorris/Documents/projects/okf
find /Users/comorris/Documents/projects/okf -maxdepth 3 -type f -print | sort
find /Users/comorris/Documents/projects/hermes-fitness/okf -maxdepth 3 -type f -print | sort
git -C /Users/comorris/Documents/projects/hermes-fitness status --short
```

Expected:
- both validations return `ok: true` with no errors;
- bundle list contains exactly Hermes Fitness;
- expected files exist;
- project `okf/` files are absent from Git status because they are ignored;
- only the intended `.gitignore` modification is visible in Hermes Fitness.

**Step 6: Record deployment evidence in the CLI repository**

Add a concise verification note to the implementation session summary. Do not commit generated OKF memory or modify any other Hermes Fitness source file.

---

## Completion checkpoint

Before claiming completion:

1. Use the `verification-before-completion` skill.
2. Run the full test/build/install commands from Task 7 with fresh output.
3. Validate both real bundles again.
4. Review `git diff` and `git status` in both `okf-cli` and `hermes-fitness`.
5. Use the `requesting-code-review` skill for a final requirements and quality review.
6. Report the generated paths, command installation options, test count, validation output, and the expected Hermes Fitness `.gitignore` change.
7. Begin a separate brainstorming/design cycle for the agent skill; do not implement the skill as an unplanned add-on.
