# Milestone v0.20.0 Cluster C: Fleet Diagnostic Truth & Concurrency Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Milestone v0.20.0 Cluster C covering the consolidated 4-point readiness matrix in `synlynk doctor --readiness`, Grok write sandbox fail-closed canary validation, post-claim story un-stranding, and SQLite WAL concurrency tuning.

**Architecture:** 
1. `synlynk/readiness.py` centralizes 4-point attestation (Role Tokens, Sandbox Egress, Policy Authority, Git Shim Integrity) with CLI table rendering and Vizor endpoint integration.
2. `synlynk/dispatch.py` adds preflight write canary validation for Grok dispatches requiring file/shell writes, failing closed or rerouting to fallback harnesses when sandboxes deny writes.
3. `synlynk/jobs.py` and `synlynk/db.py` add post-claim story un-stranding (`reclaim_stranded_stories`) to detect orphaned `in_progress` stories with dead worker PIDs and safely revert them to `ready`.
4. `synlynk/__init__.py`, `synlynk/db.py`, and `synlynk/lineage.py` standardize SQLite pragmas (`PRAGMA journal_mode = WAL`, `PRAGMA busy_timeout = 30000`, `PRAGMA synchronous = NORMAL`) to guarantee lock-free concurrent operation under multi-agent load.

**Tech Stack:** Python 3.9+, SQLite 3 (WAL mode), GitHub App JWT authentication, socket/network probes, pytest.

**Spec:** `docs/superpowers/specs/2026-09-11-v0.20.0-visual-workspace-autonomous-onboarding-design.md` §5.

---

## Global Constraints

- Python 3.9+ compatibility floor across all modules.
- Git Worktree-First Policy: All work implemented and tested in `/Users/nikhilsoman/dev/feat+v0.20.0-cluster-c-fleet-truth` on branch `feat/agy/v0.20.0-cluster-c-fleet-truth`.
- Commit trailer: `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`.
- Mandatory 4-Doc Discipline: Updates to `roadmap.md`, `devlogs/agy.md`, `costs.md`, and `memory.md`.
- No direct commit to `main`; all changes merged via PR with QA approval (`synlynk gh --role qa -- pr review ... --approve`).

---

### Task 1: Consolidated 4-Point Readiness Matrix (`synlynk doctor --readiness`, #1521)

**Files:**
- Create: `synlynk/readiness.py`
- Modify: `synlynk/cli.py`
- Modify: `synlynk/doctor.py`
- Test: `tests/test_readiness_matrix.py`

**Interfaces:**
- Produces:
  - `evaluate_readiness_matrix(repo_root: Optional[str] = None) -> dict`: Returns evaluation dictionary with 4 diagnostic points (`role_tokens`, `sandbox_egress`, `policy_authority`, `git_shim`).
  - `format_readiness_table(matrix: dict) -> str`: Formats ANSI table for CLI output.
  - `cmd_doctor_readiness(args=None) -> int`: CLI entry point for `synlynk doctor --readiness`.

- [ ] **Step 1: Write failing tests for 4-point readiness matrix**
Create `tests/test_readiness_matrix.py` asserting evaluation of all 4 points with mocked tokens, socket connections, policy files, and gh-shim paths.

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_readiness_matrix.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.readiness'`.

- [ ] **Step 3: Implement `synlynk/readiness.py`**
Implement the 4 checks:
- Point 1: Role Token Validity: Inspects `.synlynk/github_apps/<role>/` token caches, checking expiration and validity.
- Point 2: Sandbox Egress: Verifies `api.github.com:443` network egress readiness.
- Point 3: Policy Authority: Validates `.synlynk/policy.json` schema and role rules against current branch.
- Point 4: Git Shim Integrity: Checks `~/.synlynk/gh-shim/gh` existence, executable bits, and PATH precedence.
Implement `format_readiness_table()` with clean formatting.

- [ ] **Step 4: Wire `--readiness` into `synlynk/cli.py` and `synlynk/doctor.py`**
Add `--readiness` flag to `doctor_parser` in `synlynk/cli.py`. In `synlynk/doctor.py:cmd_doctor`, invoke `evaluate_readiness_matrix()` when `args.readiness` is set.

- [ ] **Step 5: Run tests to verify they pass**
Run: `pytest tests/test_readiness_matrix.py -v`
Expected: PASS.

- [ ] **Step 6: Commit Task 1**
```bash
git add synlynk/readiness.py synlynk/cli.py synlynk/doctor.py tests/test_readiness_matrix.py
git commit -m "feat(doctor): implement consolidated 4-point readiness matrix (#1521)"
```

---

### Task 2: Grok Write Sandbox Fail-Closed Canary Guard (#1522)

**Files:**
- Modify: `synlynk/dispatch.py`
- Test: `tests/test_grok_write_guard.py`

**Interfaces:**
- Produces:
  - `check_grok_sandbox_write_capability(worktree_path: str) -> bool`: Executes canary write probe in target environment.
  - Integration in `dispatch_agent()` when `agent == "grok"` and write permissions are required (`run:shell`, `run:tests`, `--requires-gh-write`, or workspace writes).

- [ ] **Step 1: Write failing tests for Grok write canary**
Create `tests/test_grok_write_guard.py` verifying that when Grok is dispatched with write requirements and canary fails, dispatch fails closed with an informative exception and sentinel alert, or falls back to Codex per policy.

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_grok_write_guard.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement Grok write canary validation in `synlynk/dispatch.py`**
Add `_canary_grok_write_access(worktree_path: str) -> bool` and invoke it prior to command execution when write capabilities are required for Grok. If canary fails, log sentinel alert and fail closed (or route to fallback harness).

- [ ] **Step 4: Run tests to verify they pass**
Run: `pytest tests/test_grok_write_guard.py -v`
Expected: PASS.

- [ ] **Step 5: Commit Task 2**
```bash
git add synlynk/dispatch.py tests/test_grok_write_guard.py
git commit -m "feat(dispatch): add Grok write sandbox fail-closed canary validation (#1522)"
```

---

### Task 3: Post-Claim Story Un-Stranding (#1507)

**Files:**
- Modify: `synlynk/jobs.py`
- Modify: `synlynk/db.py`
- Modify: `synlynk/cli.py`
- Test: `tests/test_story_unstranding.py`

**Interfaces:**
- Produces:
  - `reclaim_stranded_stories(max_age_minutes: int = 30, dry_run: bool = False, conn = None) -> List[dict]`: Reverts orphaned `in_progress` stories to `ready`.
  - Integration with `synlynk jobs reap --stories` or `synlynk story reclaim`.

- [ ] **Step 1: Write failing tests for story un-stranding**
Create `tests/test_story_unstranding.py` asserting that:
1. Stories with active running job PIDs remain `in_progress`.
2. Stories whose assigned job PID is dead and elapsed >30m are reverted to `ready` with an audit note.
3. Dry-run mode reports stranded stories without modifying SQLite.

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_story_unstranding.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `reclaim_stranded_stories` in `synlynk/jobs.py` and `synlynk/db.py`**
Implement the un-stranding logic, querying `stories` joined with `daemon_jobs`, verifying process liveness via `psutil` or `os.kill(pid, 0)`. Add CLI verb `synlynk story reclaim` and hook into `synlynk jobs reap`.

- [ ] **Step 4: Run tests to verify they pass**
Run: `pytest tests/test_story_unstranding.py -v`
Expected: PASS.

- [ ] **Step 5: Commit Task 3**
```bash
git add synlynk/jobs.py synlynk/db.py synlynk/cli.py tests/test_story_unstranding.py
git commit -m "feat(jobs): implement post-claim story un-stranding (#1507)"
```

---

### Task 4: SQLite Concurrency & Busy-Timeout Tuning (#1503)

**Files:**
- Modify: `synlynk/__init__.py`
- Modify: `synlynk/db.py`
- Modify: `synlynk/lineage.py`
- Test: `tests/test_sqlite_concurrency.py`

**Interfaces:**
- Ensures every SQLite connection executes:
  - `PRAGMA journal_mode = WAL;`
  - `PRAGMA busy_timeout = 30000;`
  - `PRAGMA synchronous = NORMAL;`

- [ ] **Step 1: Write multi-threaded concurrency stress test**
Create `tests/test_sqlite_concurrency.py` executing 20 concurrent worker threads performing rapid simultaneous reads and writes to `state.db`.

- [ ] **Step 2: Run test to observe behavior**
Run: `pytest tests/test_sqlite_concurrency.py -v`
Check if standard connections encounter busy locks without WAL/busy_timeout.

- [ ] **Step 3: Standardize SQLite connection pragmas**
In `synlynk/__init__.py:_connect`, `synlynk/db.py:_get_db`, and direct connection helpers across `synlynk/lineage.py`, inject `PRAGMA busy_timeout = 30000;` and `PRAGMA synchronous = NORMAL;`.

- [ ] **Step 4: Run tests to verify 0 lock contention**
Run: `pytest tests/test_sqlite_concurrency.py -v`
Expected: PASS with 0 database locked errors.

- [ ] **Step 5: Commit Task 4**
```bash
git add synlynk/__init__.py synlynk/db.py synlynk/lineage.py tests/test_sqlite_concurrency.py
git commit -m "perf(db): standardize SQLite WAL mode, 30s busy-timeout, and NORMAL synchronous (#1503)"
```

---

### Task 5: Integration, 4-Doc Discipline & PR Lifecycle

**Files:**
- Modify: `project-docs/roadmap.md`
- Modify: `project-docs/devlogs/agy.md`
- Modify: `project-docs/costs.md`
- Modify: `project-docs/memory.md`

- [ ] **Step 1: Run full test regression suite**
Run: `pytest tests/test_readiness_matrix.py tests/test_grok_write_guard.py tests/test_story_unstranding.py tests/test_sqlite_concurrency.py -v`
Expected: 100% PASS.

- [ ] **Step 2: Update 4-Doc Discipline files**
Update `roadmap.md` marking Cluster C complete, append devlog entry to `agy.md`, log AI token costs in `costs.md`, and record architectural decisions in `memory.md`.

- [ ] **Step 3: Open PR, execute QA review, and merge**
Push `feat/agy/v0.20.0-cluster-c-fleet-truth` to origin, open PR, verify green CI, approve via QA role (`synlynk gh --role qa -- pr review ... --approve`), squash-merge, and clean worktree.
