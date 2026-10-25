---
goal: goal-9ef9a965
epic: "#2467"
milestone: v0.25.5
arc: release-integrity
parent: "#2458"
---

# v0.25.5 — CI and Release-Integrity Stabilization Design

**Date:** 2026-10-24
**Status:** Approved (Operator sign-off 2026-10-24)
**Release target:** 2026-10-26
**Parent:** #2458 · **Release epic:** #2467 · **Goal:** goal-9ef9a965

---

## 1. Intent & Executive Summary

The `v0.25.5` release stabilizes synlynk's test execution substrate, CI pipeline throughput, and release-integrity verification. Prior daily releases surfaced race conditions in parallel test execution (`pytest -n 4`), spurious CI failures caused by volatile README test-count drift on concurrent PRs, overly broad or slow CI runner matrices, and stale diff contamination in capability calibration jobs.

This release delivers targeted fixes across five workstreams:
1. **Self-test scratch workspace concurrency & isolation (#2527, #2526):** Prevents parallel test processes from unlinking active scratch directories out from under running selftest workers.
2. **Release-docs count decoupling for in-flight PRs (#2522):** Decouples routine PR CI checks from strict `origin/main` collection count drift, while preserving strict count equality enforcement for release cuts.
3. **CI pipeline acceleration & scoped bookkeeping path filters (#2529 & Strategic Directive):** Accelerates PR CI under the 180s bar by scoping heavy test suites strictly to code and implementation specs (`docs/superpowers/**`), skipping heavy runs for pure bookkeeping diffs, and pruning redundant matrix legs.
4. **Sparse worktree cone verification (#2320, #2202):** Formally verifies and locks mandatory cone paths (`scripts`, `docs`, `bin`, `.github`, `githooks`) to prevent sparse worktree review blockers.
5. **Calibration diff-base contamination fix (#2567):** Isolates capability-sweep calibration job outputs using the job's recorded `base_sha` instead of live `origin/main` merge-base recomputes.

---

## 2. Workstream 1: Self-Test Concurrency & Workspace Isolation (#2527, #2526)

### 2.1 Problem & Root Cause
In `synlynk/doctor.py:919-938`, `cleanup_selftest_workspaces()` unconditionally searches `tempfile.gettempdir()` for directories starting with `synlynk-selftest-` and executes `shutil.rmtree` without verifying whether an active process owns the workspace.

When `pytest` executes in parallel (`-n 4 --dist loadfile`):
- Worker A running `tests/test_synlynk.py` triggers `cmd_doctor(repair=True)` (or calls `cleanup_selftest_workspaces()`).
- Worker B running `tests/test_selftest.py::test_cli_live_selftest_provisions_probe_data_before_dispatch_and_exec` creates a scratch workspace in `/tmp/synlynk-selftest-...` and executes live commands within it.
- Worker A's cleanup deletes Worker B's active directory mid-execution, causing unpredictable IOErrors, missing probe records, or `assert 1 == 0` failures.

### 2.2 Design
1. **Ownership Metadata (`.owner.json`):**
   When `_workspace_dir()` in `synlynk/selftest.py` allocates a scratch workspace, it writes `.owner.json` at the root of the scratch directory:
   ```json
   {
     "pid": 12345,
     "created_at": 1729800000.0,
     "session_id": "optional-uuid"
   }
   ```
2. **Process Liveness Verification:**
   In `cleanup_selftest_workspaces()`:
   - For each candidate directory `synlynk-selftest-*`:
     - Inspect `.owner.json`. If present:
       - Read `pid`. Check if the process is alive using `os.kill(pid, 0)` (POSIX) or equivalent.
       - If the process is alive, **skip deletion** immediately.
       - If the process is dead, check age against a minimum threshold (e.g. 60 seconds) to guard against PID reuse races, then prune.
     - If `.owner.json` is missing:
       - Check directory `mtime`. Only remove if older than 1 hour (orphaned legacy workspace).
3. **Safe Exception Handling:**
   Wrap individual workspace deletions in `shutil.rmtree(..., ignore_errors=True)` or handle `OSError` per-path so a single permission or race issue does not abort the remaining cleanup loop.

### 2.3 Verification & Test Contract
- Add `tests/test_selftest_isolation.py`:
  - Test 1: `test_cleanup_preserves_active_process_workspace`: Workspace with current `os.getpid()` is never removed.
  - Test 2: `test_cleanup_removes_dead_process_workspace`: Workspace with a nonexistent PID is safely cleaned up.
  - Test 3: `test_cleanup_preserves_recent_unowned_workspace`: Workspace without metadata but recent `mtime` (< 1 hour) is not prematurely purged.

---

## 3. Workstream 2: Release-Docs Test-Count Gate Decoupling (#2522)

### 3.1 Problem & Root Cause
In `.github/workflows/test.yml:121-141`, the `release-docs` job executes `python3 bin/synlynk.py release --check-docs` on every `pull_request`.
`validate_readme_for_release()` (`synlynk/release_readme.py:231-340`) compares README's "N tests collected" claim against live `pytest --collect-only`.

In a multi-agent workflow with concurrent dispatches:
- PR 1 and PR 2 branch from commit `A` (5,030 tests collected). Both have READMEs claiming 5,030.
- PR 1 adds 4 tests and merges to `main` (now 5,034 tests).
- PR 2's CI re-runs on its next commit or rebase attempt. `origin/main` has 5,034 tests, but PR 2's base diff or snapshot claims 5,030.
- `release-docs` fails PR 2 closed: `README claims 5030 tests collected, live collection reported 5034`, even though PR 2 did not touch `README.md` and introduced no documentation error.

### 3.2 Design
1. **PR-Mode Evaluation (`--pr-mode`):**
   Extend `validate_readme_for_release(root, expected_version, pr_mode: bool = False)`:
   - When `pr_mode=True`:
     - Inspect git diff against PR base (`git diff --name-only $BASE HEAD`):
       - If `README.md` was **not modified** in this PR:
         - Waive exact `test_count` equality; emit an informational note: `⚡ [PR-Mode] README.md untouched; test count drift against live collection bypassed for in-flight PR.`
       - If `README.md` **was modified** in this PR:
         - Verify that the count matches the PR's own branch collection.
2. **Release Authority Enforcement Preserved:**
   - Full release cuts (`synlynk release`), dry-runs (`synlynk release --dry-run`), and tag triggers (`refs/tags/v*`) run without `--pr-mode` and strictly enforce 100% exact test collection count equality.
3. **CI Workflow Integration:**
   In `.github/workflows/test.yml`:
   ```yaml
   - name: Enforce named-release README and version gate
     run: python3 bin/synlynk.py release --check-docs ${{ github.event_name == 'pull_request' && '--pr-mode' || '' }}
   ```

### 3.3 Verification & Test Contract
- Add `tests/test_release_docs_pr_mode.py`:
  - Assert `validate_readme_for_release` with `pr_mode=True` passes when `README.md` is unchanged even if live collection differs.
  - Assert `validate_readme_for_release` with `pr_mode=False` continues to fail when counts disagree.
  - Assert CLI flag `--pr-mode` is accepted by `synlynk release --check-docs`.

---

## 4. Workstream 3: CI Path Scoping & Matrix Acceleration (#2529 & Strategic Directive)

### 4.1 Problem
1. `.github/workflows/test.yml:50` uses a naive regex:
   `echo "$CHANGED" | grep -qvE '^(docs/|project-docs/|.*\.md$)'`
   This skips tests for changes in `docs/superpowers/specs/` and `docs/superpowers/plans/`, which govern real architecture and must be verified.
2. The workflow executes full test suites across 4 legs (`ubuntu-latest` and `macos-latest` on Python 3.10 and 3.12).
   macOS legs take substantial provisioning time and frequently suffer runner queues. Python 3.10 is redundant for routine PR verification when 3.12 is the primary development runtime.

### 4.2 Design
1. **Precise Bookkeeping Path Partitioning:**
   Replace the grep filter in `Detect docs-only change` with an explicit classification:
   - **Exempt Bookkeeping Paths:**
     - `project-docs/**`
     - `docs/blog/**`
     - `docs/brainstorm/**`
     - `CHANGELOG.md`
     - `.gitattributes`
     - `roadmap.md` / `todo.md`
     - `.synlynk/config.json`
   - **Mandatory Test Execution Paths:**
     - `synlynk/**`
     - `tests/**`
     - `bin/**`
     - `scripts/**`
     - `.github/**`
     - `conftest.py`
     - `docs/superpowers/**` (specs and plans)
     - `pyproject.toml`, `setup.py`, `install.sh`
   If all changed files fall within Exempt Bookkeeping Paths, set `bookkeeping_only=true` and skip install, py_compile, pytest, and fleet-matrix.
2. **Matrix Pruning & Runtime Optimization (#2529):**
   - **PR Gating Check:** Retain `test (3.12)` on `ubuntu-latest` as the required status check for pull requests.
   - **Demote 3.10 & macOS:**
     - Restrict `macos-latest` and `python-version: "3.10"` to `push` on `main`/`unstable` and manual `workflow_dispatch`.
     - This drops typical PR turnaround time below 180s without compromising branch protection safety.

### 4.3 Verification & Test Contract
- Add a workflow syntax/behavior verification test in `tests/test_ci_workflow_paths.py` verifying that the path classification script correctly categorizes:
  - `docs/superpowers/specs/x.md` -> Code/Architecture (runs test suite).
  - `project-docs/devlogs/agy.md` -> Bookkeeping (skips test suite).
  - `docs/blog/01-post.md` -> Bookkeeping (skips test suite).
  - Mixed diffs (`synlynk/cli.py` + `project-docs/todo.md`) -> Code (runs test suite).

---

## 5. Workstream 4: Sparse-Checkout Verification & Ticket Closure (#2320, #2202)

### 5.1 Problem & Prior Art
Dispatched jobs running in sparse worktrees previously failed when tests or scripts attempted to read directories outside the initial sparse cone (`scripts/`, `docs/`, `bin/`, `.github/`, `githooks/`).
PR #2361 already updated `MANDATORY_SPARSE_CONE_DIRS` in `synlynk/worktree_sparse.py:17-27`:
```python
MANDATORY_SPARSE_CONE_DIRS = (
    ".synlynk",
    "project-docs",
    "tests",
    "synlynk",
    "scripts",
    "docs",
    "bin",
    ".github",
    "githooks",
)
```
However, tickets #2320 and #2202 remain open because formal integration tests proving that sparse worktrees execute doc synchronization tests cleanly were not committed.

### 5.2 Design
1. Extend `tests/test_worktree_sparse_ast.py` with an end-to-end test initializing a real git sparse worktree via `create_sparse_cone_worktree()`.
2. Assert that:
   - `scripts/generate_command_docs.py` is present and executable.
   - `docs/reference/commands.md` and `README.md` are present.
   - `tests/test_docs_sync.py` passes inside the sparse worktree.
3. Formally close #2320 and #2202 upon PR merge.

---

## 6. Workstream 5: Calibration Diff-Base Contamination (#2567)

### 6.1 Intent & Prior Approval
Approved under `docs/superpowers/specs/2026-10-24-calibration-output-contamination-design.md`.

### 6.2 Implementation Detail
In `synlynk/capability_sweep.py:333-360`:
- Instead of recomputing `merge-base HEAD origin/main` inside the job's worktree:
  ```python
  base_sha = job.get("base_sha")
  if not base_sha:
      # Fallback to existing merge-base logic for backwards compatibility
      mb_res = subprocess.run(["git", "-C", worktree_path, "merge-base", "HEAD", "origin/main"], ...)
      base_sha = (mb_res.stdout or "").strip()
  res = subprocess.run(["git", "-C", worktree_path, "diff", base_sha], ...)
  ```
- This isolates the job's diff strictly to its own commits even when the parent dispatching process was on an ahead-of-main branch.

---

## 7. Deferred Items Allocation

The following candidate items were reviewed and explicitly assigned to downstream releases:
- **v0.25.6 Stability Closeout and Ticket Lock (milestone #14, tracked via #2535):**
  - #2573 (Review sandbox canonical state.db access)
  - #2409 (Review sandbox safety across Codex/Agy)
  - #2092 (Review-type dispatch sandbox lock write conflict)
  - #2259 (SQLite schema-change concurrency in local dispatch)
  - #2438 (Terminal outbox migration and merged PR evidence)
- **v0.26.1 Workspace-Agent Charter & Role Operations (tracked via epic #2469):**
  - #2511 (Home-harness claim mechanism collision prevention)
  - #2185 (Dispatch worktree/branch stale artifact collision)
  - #2233 (Dispatch preflight capacity gate task-typeDerivation)
  - #2133 (Dispatch stale Graphify graph + full worktree cost)

---

## 8. Capability-Based Task Allocation & Dispatch Plan

In accordance with Mode A duties and Capability-Based Task Allocation:
- **Agy (Home Conductor):** Orchestrates, verifies outputs, coordinates review and PR merges, maintains project docs, devlogs, and memory.
- **Codex (Dispatched Implementer):**
  - Task 1: Selftest concurrency guard & `.owner.json` PID tracking (#2527, #2526).
  - Task 2: Release-docs `--pr-mode` decoupling (#2522).
  - Task 3: Calibration diff-base fix (#2567).
- **Grok (Dispatched Implementer):**
  - Task 4: CI path scoping and matrix acceleration in `.github/workflows/test.yml` (#2529).
  - Task 5: Sparse worktree verification suite (#2320, #2202).

Reviewers for all generated PRs will follow the **Hardened PR Review Policy** (cross-harness + cross-model reviewer required).
