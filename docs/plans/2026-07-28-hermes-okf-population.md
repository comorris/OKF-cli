# Hermes Fitness OKF Population Implementation Plan

> **REQUIRED SUB-SKILL:** Use the executing-plans skill to implement this plan task-by-task.

**Goal:** Add provenance-aware concept creation and safe updates to `okf-cli`, then populate the Hermes Fitness bundle with exactly 20 curated, privacy-safe OKF v0.2 concepts.

**Architecture:** Add source parsing/validation as an independent domain module, extend concept creation without breaking its existing API, and implement update as a merge over parsed frontmatter that preserves unspecified fields. Build a bounded, streaming Pi archive reader for temporary ingestion, have parallel read-only synthesis agents prepare concept candidates, and serialize all bundle mutations through `okf --format json` dry-run/apply/validate cycles.

**Tech Stack:** Python 3.11+, PyYAML, argparse, pathlib, zipfile, hashlib, pytest, CodeGraph, OKF v0.2 Markdown/YAML.

**Authoritative references:**
- `docs/plans/2026-07-28-hermes-okf-population-design.md`
- <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>
- `/Users/comorris/.pi/agent/skills/okf-cli/SKILL.md`

**TDD constraint:** Implement only the tests listed in each code task. Do not add tests without revising this plan and receiving approval.

**Mutation constraint:** Never directly write files inside `/Users/comorris/Documents/projects/hermes-fitness/okf`. Use `okf-cli` for every managed concept, index, and log mutation.

---

## Phase 1: Provenance-aware CLI

### Task 1: Parse and validate OKF source metadata

**TDD scenario:** Modifying tested code — run existing tests first, then complete a red-green cycle.

**Files:**
- Create: `src/okf_cli/sources.py`
- Create: `tests/test_sources.py`
- Modify: `src/okf_cli/validation.py`
- Modify: `tests/test_validation_primitives.py`

**Authorized tests:**
1. `test_load_sources_file_accepts_yaml_list`.
2. `test_load_sources_file_accepts_json_list`.
3. `test_load_sources_file_rejects_non_list_root`.
4. `test_load_sources_file_requires_resource_per_entry`.
5. `test_load_sources_file_rejects_duplicate_ids`.
6. `test_load_sources_file_preserves_unknown_entry_fields`.
7. `test_source_validation_rejects_invalid_usage_count`.
8. `test_source_validation_rejects_invalid_last_modified`.
9. `test_source_validation_rejects_invalid_usage_window`.
10. `test_source_footnote_without_matching_id_is_warning`.
11. `test_relative_source_outside_bundle_is_allowed_when_it_exists`.
12. `test_missing_relative_source_is_warning_not_error`.
13. `test_url_and_scope_descriptor_sources_are_not_filesystem_checked`.

**Step 1: Run the baseline**

```bash
cd /Users/comorris/Documents/projects/okf-cli
.venv/bin/pytest -q
```

Expected: 77 existing tests pass before source changes.

**Step 2: Write all authorized failing tests**

Sources fixtures use this shape:

```yaml
- id: readme
  resource: ../../README.md
  title: Hermes Fitness README
  last_modified: 2026-07-18
```

Use JSON as a YAML subset for the JSON test. Include one unknown extension key and assert it survives unchanged.

**Step 3: Verify RED**

```bash
.venv/bin/pytest tests/test_sources.py tests/test_validation_primitives.py -v
```

Expected: new tests fail because `okf_cli.sources` and source validation do not exist.

**Step 4: Implement the minimal source API**

Required interface:

```python
def load_sources_file(path: Path) -> list[dict[str, Any]]: ...
def validate_sources_value(value: object, *, path: str) -> list[Finding]: ...
```

`load_sources_file` must:
- read UTF-8;
- parse with the same timestamp-preserving YAML behavior as frontmatter;
- require a top-level list;
- copy mappings without dropping unknown keys;
- require non-empty `resource` strings;
- require unique, non-empty `id` values when present;
- raise `ConfigurationError` for CLI input errors.

Validation semantics:
- `usage_count`: non-negative integer;
- `last_modified`: `YYYY-MM-DD` string;
- `usage_window`: `{from, to}` with ISO dates and `from <= to`;
- unknown keys: preserve and accept;
- unmatched body `[^label]`: warning;
- relative resources beginning with `.`, `..`, or a recognizable file suffix: check relative to the concept document, even outside the bundle;
- URLs and obvious scope descriptors: do not filesystem-check.

Avoid circular imports by moving source findings into validation or accepting a finding factory callback.

**Step 5: Verify GREEN and regression safety**

```bash
.venv/bin/pytest tests/test_sources.py tests/test_validation_primitives.py -v
.venv/bin/pytest -q
```

Expected: 13 new tests pass and all pre-existing tests remain green.

**Step 6: Commit**

```bash
git add src/okf_cli/sources.py src/okf_cli/validation.py tests/test_sources.py tests/test_validation_primitives.py
git commit -m "feat: validate OKF concept sources"
```

---

### Task 2: Add provenance to concept creation

**TDD scenario:** Modifying tested code — full red-green cycle around the existing service and CLI.

**Files:**
- Modify: `src/okf_cli/concepts.py`
- Modify: `src/okf_cli/cli.py`
- Modify: `tests/test_concepts.py`

**Authorized tests:**
1. `test_concept_create_writes_resource`.
2. `test_concept_create_writes_sources_from_service`.
3. `test_concept_create_cli_loads_sources_file`.
4. `test_concept_create_rejects_empty_resource`.
5. `test_concept_create_dry_run_includes_provenance_without_writing`.
6. `test_concept_create_with_sources_validates_end_to_end`.
7. `test_existing_create_callers_remain_compatible_without_provenance`.

**Step 1: Write the failing tests**

Add optional `resource: str | None = None` and `sources: Sequence[Mapping[str, Any]] = ()` expectations to the helper without modifying old call sites. The end-to-end test must create a real source file outside the bundle and use a correct concept-relative path.

**Step 2: Verify RED**

```bash
.venv/bin/pytest tests/test_concepts.py -v
```

Expected: new tests fail on missing arguments/options.

**Step 3: Implement minimal creation support**

Extend `_concept_metadata` and `create_concept` with optional provenance parameters at the end of signatures so existing callers remain compatible. Add CLI options:

```text
--resource RESOURCE
--sources-file PATH
```

Read and validate the sources file before instantiating `FileSystem` mutations. Preserve source entry ordering. Do not normalize user-authored resource strings during rendering.

**Step 4: Verify GREEN and full regression**

```bash
.venv/bin/pytest tests/test_concepts.py -v
.venv/bin/pytest -q
```

Expected: all authorized tests and existing suite pass.

**Step 5: Commit**

```bash
git add src/okf_cli/concepts.py src/okf_cli/cli.py tests/test_concepts.py
git commit -m "feat: create concepts with provenance"
```

---

### Task 3: Implement safe, metadata-preserving concept updates

**TDD scenario:** New feature — full TDD cycle.

**Files:**
- Modify: `src/okf_cli/concepts.py`
- Modify: `src/okf_cli/cli.py`
- Create: `tests/test_concept_update.py`

**Authorized tests:**
1. `test_update_requires_existing_concept`.
2. `test_update_changes_only_explicit_scalar_fields`.
3. `test_update_preserves_unknown_frontmatter_fields`.
4. `test_update_preserves_body_when_body_option_is_omitted`.
5. `test_update_replaces_body_when_body_file_is_supplied`.
6. `test_update_replaces_sources_only_when_sources_file_is_supplied`.
7. `test_update_preserves_sources_when_sources_file_is_omitted`.
8. `test_update_refreshes_generated_only_for_meaningful_change`.
9. `test_update_noop_writes_no_files_and_adds_no_log`.
10. `test_update_rebuilds_indexes_and_logs_once`.
11. `test_update_dry_run_reports_changes_without_writing`.
12. `test_update_cli_json_contract_and_validation`.
13. `test_update_body_and_body_file_are_mutually_exclusive`.
14. `test_update_does_not_offer_force_option`.

**Step 1: Write all failing tests**

Create fixtures containing unknown top-level and nested source fields. Freeze `now` so generated timestamp assertions are deterministic. Verify semantic metadata equality by parsing YAML, not by assuming key formatting.

**Step 2: Verify RED**

```bash
.venv/bin/pytest tests/test_concept_update.py -v
```

Expected: command/service missing.

**Step 3: Implement merge semantics**

Required service shape:

```python
_UNSET = object()

def update_concept(
    bundle_root: Path,
    concept_id: str,
    *,
    concept_type: str | object = _UNSET,
    title: str | object = _UNSET,
    description: str | object = _UNSET,
    tags: Sequence[str] | object = _UNSET,
    status: str | object = _UNSET,
    resource: str | object = _UNSET,
    sources: Sequence[Mapping[str, Any]] | object = _UNSET,
    body: str | object = _UNSET,
    generated_by: str,
    rebuild: bool,
    log_change: bool,
    fs: FileSystem,
    now: datetime | None = None,
) -> OperationResult: ...
```

Implementation order:
1. Resolve and require the existing concept path.
2. Parse the current document.
3. Deep-copy metadata.
4. Apply only non-`_UNSET` fields.
5. Validate the proposed concept before writing.
6. Compare proposed metadata/body while excluding `generated` from the change decision.
7. Return `updated: false` with no filesystem changes for a no-op.
8. On change, set `generated`, atomically write, rebuild indexes, and append one Update log entry.

CLI `concept update` options mirror create, except `--type` is optional and no `--force` exists. `--tag` defaults to `None` so omission differs from replacement. Omitted body preserves body; explicit `--body ""` clears it.

**Step 4: Verify GREEN and full suite**

```bash
.venv/bin/pytest tests/test_concept_update.py -v
.venv/bin/pytest -q
```

Expected: all 14 tests pass and no regression.

**Step 5: Commit**

```bash
git add src/okf_cli/concepts.py src/okf_cli/cli.py tests/test_concept_update.py
git commit -m "feat: safely update OKF concepts"
```

---

### Task 4: Complete CLI integration, docs, and agent-skill guidance

**TDD scenario:** Modifying tested code — baseline first, then targeted integration tests.

**Files:**
- Modify: `README.md`
- Modify: `tests/test_end_to_end.py`
- Modify: `tests/test_cli_contract.py`
- Modify: `/Users/comorris/.pi/agent/skills/okf-cli/SKILL.md`

**Authorized tests:**
1. `test_help_documents_create_provenance_options`.
2. `test_help_documents_concept_update_without_force`.
3. `test_end_to_end_create_update_validate_preserves_extensions`.
4. `test_invalid_sources_file_returns_configuration_exit_three`.
5. `test_update_missing_concept_returns_configuration_exit_three`.
6. `test_json_error_envelope_remains_stable_for_update`.

**Step 1: Run baseline and write failing tests**

```bash
.venv/bin/pytest -q
```

Then add exactly the six tests above.

**Step 2: Verify RED**

```bash
.venv/bin/pytest tests/test_end_to_end.py tests/test_cli_contract.py -v
```

Expected: help/docs or edge handling failures.

**Step 3: Finish command behavior and README**

Document sources-file schema, update merge semantics, examples, exit behavior, and compatibility. Update the global `okf-cli` skill using the skill-creator conventions so it:
- uses `--sources-file` for synthesized concepts;
- uses `concept update` rather than `create --force`;
- previews update, applies exact command, validates, and reports no-ops;
- preserves its prohibition on direct bundle edits.

Do not add helper files to the skill.

**Step 4: Verify GREEN and build/install**

```bash
.venv/bin/pytest -q
rm -rf build dist
.venv/bin/python -m build
python3 -m venv /tmp/okf-cli-wheel-test
/tmp/okf-cli-wheel-test/bin/pip install dist/*.whl
/tmp/okf-cli-wheel-test/bin/okf concept update --help
```

Expected: full suite passes, artifacts build, wheel installs, update help contains no `--force`.

Validate the skill frontmatter with PyYAML and verify its directory/name match.

**Step 5: Commit repository changes**

```bash
git add README.md src tests
git commit -m "docs: document provenance and safe updates"
```

The global skill is outside the repository; report its validated path separately.

---

## Phase 2: Deterministic source preparation

### Task 5: Build a bounded Pi conversation archive inventory/extractor

**TDD scenario:** New support utility — full TDD cycle.

**Files:**
- Create: `src/okf_cli/pi_archive.py`
- Create: `scripts/extract_pi_archive.py`
- Create: `tests/test_pi_archive.py`

**Authorized tests:**
1. `test_archive_inventory_is_sorted_and_includes_sha256_size_and_timestamp`.
2. `test_archive_reader_never_calls_extract`.
3. `test_archive_reader_keeps_only_user_and_assistant_text_parts`.
4. `test_archive_reader_excludes_tool_results_calls_and_thinking_events`.
5. `test_archive_reader_skips_oversized_jsonl_records_with_diagnostic_count`.
6. `test_archive_reader_rejects_non_jsonl_members`.
7. `test_archive_output_is_deterministic_across_runs`.
8. `test_script_writes_only_to_explicit_output_outside_bundle`.
9. `test_script_refuses_output_inside_bundle`.

**Step 1: Write failing tests with tiny synthetic ZIP fixtures**

Do not use the 60 MB real archive in unit tests. Include one oversized record and mixed Pi event types.

**Step 2: Verify RED**

```bash
.venv/bin/pytest tests/test_pi_archive.py -v
```

Expected: module/script missing.

**Step 3: Implement streaming extraction**

Required API:

```python
@dataclass(frozen=True)
class ArchiveMember: ...
@dataclass(frozen=True)
class SessionText: ...

def inventory_archive(path: Path) -> list[ArchiveMember]: ...
def iter_session_text(path: Path, *, max_record_bytes: int) -> Iterator[SessionText]: ...
```

Rules:
- use `ZipFile.open`, never `extract`/`extractall`;
- process members in normalized sorted order;
- read JSONL with a bounded-line iterator using `readline(max_record_bytes + 1)` and drain oversized records without parsing;
- retain only `message` events with role `user` or `assistant` and textual content parts;
- skip tool-call/tool-result content and all non-message events;
- record archive/member SHA-256, size, timestamp, session ID, and skipped-record count;
- write JSON inventory and filtered JSONL only to an explicit temporary output directory outside any supplied bundle root.

The script is an ingestion support utility, not a new public `okf` subcommand.

**Step 4: Verify GREEN and run against the real archive**

```bash
.venv/bin/pytest tests/test_pi_archive.py -v
rm -rf /tmp/hermes-okf-population
.venv/bin/python scripts/extract_pi_archive.py \
  --archive /Users/comorris/Documents/projects/hermes-fitness/okf/iphone-fitness-app-pi-conversations.zip \
  --bundle /Users/comorris/Documents/projects/hermes-fitness/okf \
  --out /tmp/hermes-okf-population/conversations \
  --max-record-bytes 2097152
```

Expected: 40 JSONL members inventoried, no archive extraction tree, oversized records counted rather than loaded, and output exists only below `/tmp/hermes-okf-population`.

**Step 5: Commit**

```bash
git add src/okf_cli/pi_archive.py scripts/extract_pi_archive.py tests/test_pi_archive.py
git commit -m "feat: stream Pi conversation archives safely"
```

---

## Phase 3: Hermes concept synthesis and ingestion

### Task 6: Create 12 current-state overview, architecture, interface, and domain concepts

**TDD scenario:** Knowledge-content task — do not add code tests. Validate every CLI batch.

**Managed concepts:**

| ID | Type | Status | Primary evidence |
|---|---|---|---|
| `overview/project-overview` | Project Overview | stable | `README.md`, `pyproject.toml` |
| `overview/privacy-security-boundary` | Policy | stable | README privacy/auth warnings, config behavior |
| `architecture/system-overview` | Architecture | stable | `app/`, API entry point, iOS app structure, tests |
| `architecture/data-persistence` | Data Model | stable | `app/db.py`, `app/models.py`, model/db tests |
| `architecture/synchronization` | Architecture | stable | health/nutrition/workout sync services and iOS sync code |
| `interfaces/backend-api` | API Reference | stable | `app/api/*.py`, API tests |
| `interfaces/hermes-tools` | Interface Reference | stable | `app/tools/hermes_tools.py`, `docs/hermes-tools.md`, tests |
| `interfaces/ios-application` | Architecture | stable | iOS source/tests, README iOS section |
| `domains/nutrition` | Domain Guide | stable | nutrition routes/services/models/tests |
| `domains/recipes` | Domain Guide | stable | recipe services/routes/models/tests and current plans |
| `domains/workouts` | Domain Guide | stable | workout services/routes/models/tests and iOS workout code |
| `domains/health-body-metrics` | Domain Guide | stable | health/body routes/services/models/tests |

**Step 1: Prepare a temporary synthesis workspace**

```bash
rm -rf /tmp/hermes-okf-population/concepts
mkdir -p /tmp/hermes-okf-population/concepts
```

No temporary candidate may be written inside the bundle.

**Step 2: Dispatch read-only synthesis agents in parallel**

Use CodeGraph first for each domain. Assign disjoint concept groups:
- Agent A: overview + privacy.
- Agent B: architecture concepts.
- Agent C: interfaces.
- Agent D: domains.

Each agent writes candidate `body.md` and `sources.yaml` only under its assigned `/tmp/hermes-okf-population/concepts/<concept-id>/`. Agents must not mutate the OKF bundle.

**Required body structure:**

```markdown
# Purpose
# Current Behavior
# Boundaries and Invariants
# Relationships
# Operational Implications
# Known Gaps
```

Omit inapplicable headings. Use source-ID footnotes for material claims. Do not copy long source passages.

**Step 3: Review source authority and privacy before mutation**

For every stable claim, require at least one code/test/current-doc source. Reject personal values, credentials, raw transcript text, and unsupported future behavior. Ensure source resource paths are correct relative to the final concept file.

**Step 4: Serialize CLI writes through one writer agent**

For each concept in table order:
1. Run `okf --format json concept create ... --sources-file ... --body-file ... --generated-by process:hermes-okf-ingestion --dry-run`.
2. Inspect exit 0, `ok: true`, empty errors, and exact target path.
3. Apply the identical command without `--dry-run`.
4. Run `okf --format json validate --bundle /Users/comorris/Documents/projects/hermes-fitness/okf`.
5. Stop on any error; record and review warnings.

Do not use `--force`, `--no-index`, or `--no-log`.

**Step 5: Verify the batch**

```bash
okf --format json validate --bundle /Users/comorris/Documents/projects/hermes-fitness/okf
find /Users/comorris/Documents/projects/hermes-fitness/okf -name '*.md' -print | sort
```

Expected: all 12 concepts exist plus reserved/bundle files; validation has zero errors.

---

### Task 7: Create 8 operational, decision, history, and reference concepts

**TDD scenario:** Knowledge-content task — do not add code tests. Validate every CLI batch.

**Managed concepts:**

| ID | Type | Status | Primary evidence |
|---|---|---|---|
| `operations/setup-configuration` | Runbook | stable | README setup, `.env.example`, config tests |
| `operations/testing` | Testing Guide | stable | README, `pyproject.toml`, Python and iOS tests |
| `operations/server-recovery` | Runbook | stable | server manager, restart script/tests, troubleshooting docs |
| `troubleshooting/sync-tombstones` | Troubleshooting Guide | stable | nutrition/workout sync code/tests and reliability docs |
| `decisions/local-first-idempotency` | Architecture Decision | stable | current code/tests, README, implemented design notes |
| `history/project-evolution` | Historical Summary | stable | thematic plans plus selected archive sessions |
| `history/open-questions` | Open Questions | draft | README known gaps, unimplemented plans, conversations corroborated by code absence |
| `references/source-inventory` | Reference | stable | deterministic repository/archive inventory |

**Step 1: Inventory repository documentation**

Create `/tmp/hermes-okf-population/source-inventory.json` containing relative path, category, Git last-modified date, size, and SHA-256 for README/docs/plans/troubleshooting/examples. Ignore caches, egg-info, virtualenvs, generated bundle concepts, and personal data stores.

**Step 2: Dispatch parallel read-only synthesis agents**

- Agent E: setup, testing, server recovery.
- Agent F: sync/tombstone troubleshooting and local-first decision.
- Agent G: thematic plan classification and project evolution.
- Agent H: conversation-derived decisions/open questions using filtered temporary JSONL.
- Agent I: source inventory concept.

Conversation agents must cite archive member IDs, not quote raw text. A conversation-only claim must be labeled rationale/history/open question, never stable current behavior.

**Step 3: Reconcile history against current code**

Review proposed completed/superseded/open statuses against code/tests and recent implementation notes. Remove any “open” item already implemented. Mark uncertainty explicitly.

**Step 4: Serialize CLI writes**

Use the same dry-run → inspect → apply → validate sequence from Task 6, in table order. Use `process:hermes-okf-ingestion`. Do not use direct edits or force.

**Step 5: Remove temporary conversation text**

After all concepts are applied and provenance member IDs are confirmed:

```bash
rm -rf /tmp/hermes-okf-population/conversations
```

Retain no raw/filtered transcript copy in the OKF bundle.

**Step 6: Verify exactly 20 managed concepts**

Count non-reserved Markdown files excluding `bundle.md`. Expected: exactly the 20 IDs listed in Tasks 6–7. Validate the bundle with zero errors.

---

### Task 8: Final privacy, provenance, link, and quality audit

**TDD scenario:** Verification task — do not add tests or concepts unless correcting a reviewed defect through `concept update`.

**Step 1: Rebuild indexes through the CLI**

```bash
okf --format json index rebuild \
  --bundle /Users/comorris/Documents/projects/hermes-fitness/okf \
  --dry-run
```

Inspect, then apply only if changes are expected. Validate afterward.

**Step 2: Audit taxonomy and progressive disclosure**

Verify root and nested indexes list all 20 concepts with descriptions, deterministic ordering, and useful grouping. Check duplicate titles and near-duplicate sections.

**Step 3: Audit provenance**

For every concept:
- `sources` exists and each entry has `resource`;
- footnote source IDs resolve;
- current stable claims have code/test/current-doc evidence;
- relative file sources exist;
- archive references identify exact JSONL members;
- no concept claims raw conversation as authoritative current behavior.

**Step 4: Audit links**

Run validation and independently scan Markdown links. Review every warning. Correct content only with `okf concept update` dry-run/apply/validate.

**Step 5: Audit privacy and secrets**

Scan generated Markdown for high-risk secret forms:

```bash
rg -n --glob '*.md' \
  'AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|-----BEGIN .*PRIVATE KEY-----|Bearer [A-Za-z0-9._~+/=-]{16,}' \
  /Users/comorris/Documents/projects/hermes-fitness/okf
```

Review all occurrences of numeric health units and personal-record language:

```bash
rg -n --glob '*.md' \
  '[0-9]+([.][0-9]+)?[[:space:]]*(lb|lbs|kg|bpm|kcal)|blood pressure|meal record|workout record' \
  /Users/comorris/Documents/projects/hermes-fitness/okf
```

Technical field names and generic behavior are allowed; user-specific values or records are not.

**Step 6: Run fresh CLI verification**

```bash
cd /Users/comorris/Documents/projects/okf-cli
.venv/bin/pytest -q
rm -rf build dist
.venv/bin/python -m build
okf --version
okf --format json validate --bundle /Users/comorris/Documents/projects/hermes-fitness/okf
okf --format json validate --bundle /Users/comorris/Documents/projects/okf
okf --format json bundle list --catalog /Users/comorris/Documents/projects/okf
```

Expected:
- all CLI tests pass;
- package builds;
- both bundles have zero validation errors;
- catalog lists Hermes Fitness exactly once.

**Step 7: Review repository states**

```bash
git -C /Users/comorris/Documents/projects/okf-cli status --short --branch
git -C /Users/comorris/Documents/projects/okf-cli diff main...HEAD --stat
git -C /Users/comorris/Documents/projects/hermes-fitness status --short --branch
git -C /Users/comorris/Documents/projects/hermes-fitness check-ignore -v okf/bundle.md
```

Expected: CLI changes are committed on `feat/okf-provenance-population`; Hermes OKF content is ignored; only the intended Hermes `.gitignore` change is visible.

**Step 8: Request review before completion**

Use `requesting-code-review` twice:
1. CLI requirements/code-quality review.
2. Knowledge quality/privacy/provenance review.

Address findings using TDD for code and `concept update` for knowledge. Then rerun Step 6 before claiming completion.
