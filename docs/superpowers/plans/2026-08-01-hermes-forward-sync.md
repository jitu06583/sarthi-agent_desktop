# Hermes Forward Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a safe, testable daily workflow that detects future Hermes changes and opens a non-self-merging draft synchronization PR with review artifacts.

**Architecture:** A dependency-free Python generator fetches Hermes into an isolated ref, validates the accepted baseline, and emits deterministic reports plus a binary-capable patch. A GitHub Actions workflow runs the generator, skips when a sync PR is already open, and creates one protected draft branch and PR using only the repository `GITHUB_TOKEN`.

**Tech Stack:** Python 3.11 standard library, Git CLI, unittest, GitHub Actions YAML, GitHub CLI available on GitHub-hosted runners.

## Global Constraints

- Preserve the current Sarthi source tree and do not port the historical Hermes backlog.
- Never auto-merge raw Hermes code or advance the accepted baseline automatically.
- Do not modify the live installed Sarthi checkout.
- Use `NousResearch/hermes-agent` branch `main` as the authoritative upstream.
- Use one open draft sync PR at a time; scheduled runs must not overwrite reviewer changes.
- Require no personal GitHub token or paid service.

---

### Task 1: Deterministic Hermes sync generator

**Files:**
- Create: `tests/scripts/test_hermes_sync.py`
- Create: `scripts/hermes_sync.py`

**Interfaces:**
- Consumes: Git repository, baseline path, upstream URL, upstream branch, output directory.
- Produces: CLI exit code; `GITHUB_OUTPUT` values `updated`, `upstream_sha`, and `commit_count`; generated `REPORT.md`, `commits.tsv`, `changed-files.tsv`, `upstream.patch`, and `candidate-baseline`.
- Public Python entry point: `main(argv: Sequence[str] | None = None) -> int`.

- [ ] **Step 1: Write failing end-to-end tests**

Create a `unittest.TestCase` that uses temporary local Git repositories and subprocess Git calls. Tests must assert:

```python
def test_rejects_invalid_baseline(self): ...
def test_no_update_writes_no_pending_artifacts(self): ...
def test_update_writes_report_patch_and_candidate(self): ...
def test_rejects_non_ancestor_baseline(self): ...
```

The update fixture must create a baseline commit and one later upstream commit, invoke `python scripts/hermes_sync.py --upstream-url <local-bare-repo>`, and assert that the report contains both SHAs, the candidate equals the tip, and the patch contains the added file.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m unittest tests.scripts.test_hermes_sync -v
```

Expected: FAIL because `scripts/hermes_sync.py` does not exist.

- [ ] **Step 3: Implement the minimal generator**

Implement:

```python
def run_git(repo: Path, *args: str, capture_bytes: bool = False) -> str | bytes: ...
def read_baseline(path: Path) -> str: ...
def set_github_outputs(updated: bool, upstream_sha: str, commit_count: int) -> None: ...
def generate(repo: Path, baseline_file: Path, upstream_url: str,
             upstream_branch: str, output_dir: Path) -> bool: ...
def main(argv: Sequence[str] | None = None) -> int: ...
```

Required behavior:

- validate `^[0-9a-f]{40}$`;
- fetch with `git fetch --no-tags <url> +refs/heads/<branch>:refs/remotes/hermes-sync/upstream`;
- verify commit existence and ancestry with `git cat-file -e` and `git merge-base --is-ancestor`;
- remove stale pending output before generation;
- return a successful no-op when baseline equals upstream;
- generate deterministic UTF-8 text files and `git format-patch --binary --stdout baseline..upstream`;
- write `GITHUB_OUTPUT` only when that environment variable exists;
- report actionable failures through `HermesSyncError` and exit 1.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
python -m unittest tests.scripts.test_hermes_sync -v
python -m py_compile scripts/hermes_sync.py tests/scripts/test_hermes_sync.py
```

Expected: four tests pass and syntax compilation exits 0.

- [ ] **Step 5: Commit generator and tests**

```bash
git add scripts/hermes_sync.py tests/scripts/test_hermes_sync.py
git commit -m "feat: generate Hermes forward-sync artifacts"
```

---

### Task 2: Baseline, workflow, and maintainer instructions

**Files:**
- Create: `.github/hermes-sync/baseline`
- Create: `.github/hermes-sync/README.md`
- Create: `.github/workflows/hermes-forward-sync.yml`
- Modify: `docs/superpowers/specs/2026-08-01-hermes-forward-sync-design.md`
- Test: `tests/scripts/test_hermes_sync_workflow.py`

**Interfaces:**
- Consumes: Task 1 CLI and its `GITHUB_OUTPUT` contract.
- Produces: daily/manual workflow and maintainer review procedure.

- [ ] **Step 1: Write failing workflow contract tests**

Create tests that load the workflow as text and assert exact safety contracts:

```python
def test_workflow_has_manual_and_daily_triggers(self): ...
def test_workflow_uses_minimum_write_permissions(self): ...
def test_workflow_skips_when_sync_pr_is_open(self): ...
def test_workflow_creates_draft_pr_without_auto_merge(self): ...
def test_baseline_is_full_sha(self): ...
```

The tests must reject `pull_request_target`, broad `write-all`, and any `gh pr merge` command.

- [ ] **Step 2: Run tests and verify RED**

```bash
python -m unittest tests.scripts.test_hermes_sync_workflow -v
```

Expected: FAIL because the baseline and workflow files do not exist.

- [ ] **Step 3: Add accepted baseline and workflow**

Write the exact fetched Hermes tip to `.github/hermes-sync/baseline`.

The workflow must include:

```yaml
on:
  schedule:
    - cron: "17 4 * * *"
  workflow_dispatch: {}
permissions:
  contents: write
  pull-requests: write
concurrency:
  group: hermes-forward-sync
  cancel-in-progress: false
```

Steps must:

1. checkout `main` with full history;
2. query `gh pr list --head automation/hermes-forward-sync --state open` and skip if one exists;
3. run `python scripts/hermes_sync.py` with `id: sync`;
4. only when `steps.sync.outputs.updated == 'true'`, configure the Actions bot identity, create `automation/hermes-forward-sync`, commit generated files, push the branch, and run `gh pr create --draft`;
5. never merge or advance `.github/hermes-sync/baseline`.

- [ ] **Step 4: Add maintainer instructions**

Document how to inspect `REPORT.md`, apply or port `upstream.patch`, add tests, replace the accepted baseline with `candidate-baseline`, and merge only after review.

- [ ] **Step 5: Run workflow tests and YAML parse**

```bash
python -m unittest tests.scripts.test_hermes_sync_workflow -v
python -c "import pathlib,yaml; yaml.safe_load(pathlib.Path('.github/workflows/hermes-forward-sync.yml').read_text(encoding='utf-8'))"
```

Expected: all tests pass and YAML parsing exits 0.

- [ ] **Step 6: Commit workflow**

```bash
git add .github/hermes-sync .github/workflows/hermes-forward-sync.yml tests/scripts/test_hermes_sync_workflow.py docs/superpowers/specs/2026-08-01-hermes-forward-sync-design.md
git commit -m "ci: add reviewed Hermes forward synchronization"
```

---

### Task 3: End-to-end verification and publication

**Files:**
- Modify only if verification finds defects in files created by Tasks 1–2.

**Interfaces:**
- Consumes: complete feature branch.
- Produces: verified commit, pushed GitHub branch, pull request, and Multica completion comment.

- [ ] **Step 1: Run the complete focused suite**

```bash
python -m unittest discover -s tests/scripts -p 'test_hermes_sync*.py' -v
python -m py_compile scripts/hermes_sync.py tests/scripts/test_hermes_sync.py tests/scripts/test_hermes_sync_workflow.py
python -c "import pathlib,yaml; yaml.safe_load(pathlib.Path('.github/workflows/hermes-forward-sync.yml').read_text(encoding='utf-8'))"
git diff --check main...HEAD
git status --short --branch
```

Expected: tests pass, compilation and YAML parsing exit 0, no whitespace errors, and no uncommitted files.

- [ ] **Step 2: Verify real upstream no-update behavior**

Run the generator against `https://github.com/NousResearch/hermes-agent.git` with the accepted baseline equal to the fetched upstream tip.

Expected: exit 0, `updated=false`, and no pending directory.

- [ ] **Step 3: Push branch**

```bash
git push -u origin ci/hermes-upstream-sync
```

Expected: remote branch created successfully.

- [ ] **Step 4: Create GitHub pull request**

Use GitHub CLI if authenticated; otherwise use the GitHub REST API with an already configured credential. Create a PR titled `ci: add safe Hermes forward synchronization`, base `main`, head `ci/hermes-upstream-sync`, and include test evidence and the explicit no-backlog/no-auto-merge guarantees.

- [ ] **Step 5: Verify remote PR and CI**

Read the PR URL and checks from GitHub. If checks fail, inspect logs, fix, re-run local verification, commit, and push up to three repair attempts.

- [ ] **Step 6: Update Multica**

Move `SAR-5` to `in_review` while the GitHub PR awaits merge, or `done` if merged. Add a comment with the repository, branch, PR URL, test evidence, and any remaining authorization requirement.
