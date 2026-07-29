# OKF CLI Skill Packaging Implementation Plan

> **REQUIRED SUB-SKILL:** Use the executing-plans skill to implement this plan task-by-task.

**Goal:** Package the updated `okf-cli` Pi skill with the CLI repository, synchronize the installed global copy, and publish it from GitHub.

**Architecture:** Use Pi's conventional `skills/<name>/SKILL.md` discovery so the Python repository needs no Node manifest. Keep the repository skill authoritative and copy it byte-for-byte to the global skill directory after validation.

**Tech Stack:** Markdown, YAML frontmatter, Bash, Python 3.11, pytest, Pi git packages.

---

### Task 1: Add the canonical packaged skill

**TDD scenario:** Trivial documentation/package change — use judgment.

**Files:**
- Create: `skills/okf-cli/SKILL.md`
- Reference: `/Users/comorris/.pi/agent/skills/okf-cli/SKILL.md`
- Reference: `scripts/extract_pi_archive.py`

**Step 1: Copy the current global skill into the conventional package path**

```bash
mkdir -p skills/okf-cli
cp /Users/comorris/.pi/agent/skills/okf-cli/SKILL.md skills/okf-cli/SKILL.md
```

**Step 2: Update setup and capability checks**

Require `okf-cli 0.2.0+`, then inspect `concept create --help` and `concept update --help` for `--resource` and `--sources-file`; reject an update command exposing `--force`. Document explicit uv reinstallation for stale tools.

**Step 3: Correct the provenance example**

Initialize `sources_file="$(mktemp)"` before writing YAML and require cleanup of both temporary files.

**Step 4: Add bounded conversation archive ingestion guidance**

Invoke `{baseDir}/../../scripts/extract_pi_archive.py`. State that output is a directory outside the bundle, all JSONL sessions are emitted after event filtering, malformed and oversized records increment `skipped_records`, and temporary data must be deleted after privacy-conscious synthesis.

**Tests:**
- Frontmatter test: parse the first YAML block and expect `name: okf-cli` and a non-empty description.
- Package-discovery test: expect `skills/okf-cli/SKILL.md` to exist.
- Reference test: resolve `{baseDir}/../../scripts/extract_pi_archive.py` from the skill directory and expect a file.
- Content test: expect setup to mention `0.2.0`, both provenance flags, `concept update`, no-force validation, archive cleanup, and authority/privacy rules.

**Step 5: Commit**

```bash
git add skills/okf-cli/SKILL.md
git commit -m "feat: package updated OKF CLI skill"
```

### Task 2: Document Pi package installation

**TDD scenario:** Trivial documentation change — use judgment.

**Files:**
- Modify: `README.md`

**Step 1: Add a Pi skill installation section**

Document:

```bash
pi install git:github.com/comorris/OKF-cli
```

Include `/skill:okf-cli`, the `0.2.0+` CLI prerequisite, and the distinction between installing the skill and installing the `okf` executable.

**Tests:**
- README content test: expect the Git package source and exact skill invocation.
- Command accuracy test: compare documented CLI options with `okf concept create --help` and `okf concept update --help`.

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document Pi skill installation"
```

### Task 3: Synchronize and validate the installed skill

**TDD scenario:** Trivial installation synchronization — use judgment.

**Files:**
- Modify: `/Users/comorris/.pi/agent/skills/okf-cli/SKILL.md`

**Step 1: Copy the validated canonical skill to the global location**

```bash
cp skills/okf-cli/SKILL.md /Users/comorris/.pi/agent/skills/okf-cli/SKILL.md
```

**Step 2: Verify exact synchronization**

```bash
cmp skills/okf-cli/SKILL.md /Users/comorris/.pi/agent/skills/okf-cli/SKILL.md
```

**Step 3: Verify runtime capabilities**

Run `okf --version`, inspect create/update help, ensure required provenance options exist, and ensure update lacks `--force`.

**Step 4: Run repository tests**

```bash
.venv/bin/pytest -q
```

Expected: all tests pass with zero failures.

### Task 4: Review, merge, and publish

**TDD scenario:** Verification and release task — no implementation test.

**Files:**
- Review all changes from `main...feat/package-okf-cli-skill`.

**Step 1: Run final hygiene and package checks**

Run `git diff --check`, the skill validation checks listed above, exact global comparison, and the complete pytest suite.

**Step 2: Request an independent read-only review**

Require resolution of all Critical and Important findings before proceeding.

**Step 3: Merge locally**

Fast-forward or merge the feature branch into `main`, rerun the complete pytest suite, then delete the feature branch.

**Step 4: Push without force**

```bash
git push origin main
```

**Step 5: Verify publication**

Compare `git rev-parse main` with `git ls-remote origin refs/heads/main` and confirm they match.
