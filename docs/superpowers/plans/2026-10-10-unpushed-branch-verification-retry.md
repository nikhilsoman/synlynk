# `_guard_unpushed_branch` Inconclusive-Verification Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `_guard_unpushed_branch` from collapsing an inconclusive GitHub check (`None`) into a committed `STATUS_UNPUSHED_BRANCH` on the first hiccup — give it the same bounded-retry-then-settle machinery `_apply_gh_write_verification` already has, and wire the daemon's reconciliation loop to defer settlement while retries remain.

**Architecture:** Add a persisted per-job attempt counter (`daemon_jobs.unpushed_branch_check_attempts`) and a retry cap constant. Rewrite `_guard_unpushed_branch` to treat `github_branch_effect_verified()`'s three possible outcomes (`True`/`False-via-exhaustion`/`None`-while-retrying) distinctly instead of collapsing `None` and "not pushed" together. Add a new `_unpushed_branch_retry_pending()` helper, structurally mirroring `_gh_write_verification_retry_pending()`, and call it at all 3 existing `_guard_unpushed_branch` call sites inside `_reconcile_daemon_jobs`, deferring terminal settlement (`continue`) exactly like the existing GH-write-verification retry check two statements later at each site.

**Tech Stack:** Python 3 stdlib only (`sqlite3`), pytest, `monkeypatch`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-10-unpushed-branch-verification-retry-design.md` (committed, approved).

---

## Important implementation note: the 3 call sites do NOT all commit the same way

The spec's call-site snippet shows a uniform `conn.commit(); continue` pattern. Reading the real code shows **two different commit idioms** depending on which call site:

- **Site 1 (`jobs.py:4283`, preferred-summary path)** and **Site 3 (`jobs.py:4454`, normal ground-truth-verification path)**: plain `conn.commit(); continue`, matching the existing `_gh_write_verification_retry_pending` pattern at those same sites.
- **Site 2 (`jobs.py:4386`, zombie-reap path)**: this branch has already called `_claim_daemon_job_terminal(conn, job_id)` and holds a `terminal_claim_token`. Deferring here must release that claim via `_release_daemon_job_terminal_claim_and_commit(conn, job_id, terminal_claim_token)` — a bare `conn.commit()` would leave the claim held and block every other reconciler pass from ever retrying this job. This exactly matches how the existing `_gh_write_verification_retry_pending` check is handled at this same site a few lines below (see `jobs.py:4400-4406`).

Task 3 below wires each site with its correct idiom — do not copy-paste the same two lines into all three.

---

## File Structure

- **Modify `synlynk/db.py`** — add one idempotent column migration (Task 1).
- **Modify `synlynk/jobs.py`** — add constant, rewrite `_guard_unpushed_branch`, add `_unpushed_branch_retry_pending`, wire 3 call sites (Tasks 2–3).
- **Modify `tests/test_jobs.py`** — add unit tests for the rewritten guard, the new helper, and the call-site wiring (Tasks 2–3, TDD-first).

---

### Task 1: `daemon_jobs.unpushed_branch_check_attempts` migration

**Files:**
- Modify: `synlynk/db.py:1302-1309` (insert new block immediately after the existing `gh_write_verification_attempts` block)

- [ ] **Step 1: Add the migration block**

In `synlynk/db.py`, immediately after the existing block ending at line 1309 (the `gh_write_verification_attempts` column addition), insert:

```python
        if "unpushed_branch_check_attempts" not in daemon_job_cols:
            try:
                conn.execute(
                    "ALTER TABLE daemon_jobs ADD COLUMN "
                    "unpushed_branch_check_attempts INTEGER NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass
```

(Match the exact indentation of the surrounding `if "gh_write_verification_attempts" ...` block — 8 spaces for the `if`, consistent with the rest of that migration function.)

- [ ] **Step 2: Verify the migration runs cleanly on a fresh DB**

Run: `python3 -c "
import tempfile, os, sqlite3
os.chdir(tempfile.mkdtemp())
os.makedirs('project-docs/devlogs')
os.makedirs('.synlynk')
import synlynk as sl
conn = sl._get_db()
cols = [r[1] for r in conn.execute('PRAGMA table_info(daemon_jobs)').fetchall()]
assert 'unpushed_branch_check_attempts' in cols, cols
print('OK:', 'unpushed_branch_check_attempts' in cols)
"`

Expected: `OK: True`, no traceback.

- [ ] **Step 3: Commit**

```bash
git add synlynk/db.py
git commit -m "feat(db): add unpushed_branch_check_attempts column migration (gh:#2136, #2137, #2130)"
```

---

### Task 2: Rewrite `_guard_unpushed_branch` with bounded retry + new `_unpushed_branch_retry_pending` helper

**Files:**
- Modify: `synlynk/jobs.py:36-37` (new constant, next to `_GH_WRITE_VERIFICATION_RETRY_CAP`)
- Modify: `synlynk/jobs.py:4021-4040` (rewrite `_guard_unpushed_branch`)
- Modify: `synlynk/jobs.py` (new `_unpushed_branch_retry_pending` function, placed immediately after `_gh_write_verification_retry_pending`, i.e. after current line 3885)
- Test: `tests/test_jobs.py` (new tests, placed near the existing `test_unpushed_guard_accepts_pr_delivery_after_head_branch_deletion` at line 2081)

- [ ] **Step 1: Write the failing tests**

Add these tests to `tests/test_jobs.py`, directly after `test_unpushed_guard_accepts_pr_delivery_after_head_branch_deletion` (ends at line 2093):

```python
def test_unpushed_guard_retries_on_inconclusive_check_instead_of_settling(monkeypatch):
    import sqlite3
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(jobs_mod, "local_commits_pushed", lambda *args: False)
    monkeypatch.setattr(jobs_mod, "github_branch_effect_verified", lambda *args, **kwargs: None)

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, status TEXT, "
        "gh_write_verified TEXT, unpushed_branch_check_attempts INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute("INSERT INTO daemon_jobs (job_id, status) VALUES ('job-retry', 'done')")
    conn.commit()

    state = {"commits_ahead": 1, "base_commit": "base-sha"}

    for expected_attempts in (1, 2, 3):
        result = jobs_mod._guard_unpushed_branch(
            conn, "job-retry", "done", "/tmp/missing-worktree", "fix/job-retry", state,
            "2026-10-04T09:00:00",
        )
        assert result == "done"
        attempts = conn.execute(
            "SELECT unpushed_branch_check_attempts FROM daemon_jobs WHERE job_id='job-retry'"
        ).fetchone()[0]
        assert attempts == expected_attempts

    conn.close()


def test_unpushed_guard_settles_unpushed_after_retry_cap_exhausted(monkeypatch):
    import sqlite3
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(jobs_mod, "local_commits_pushed", lambda *args: False)
    monkeypatch.setattr(jobs_mod, "github_branch_effect_verified", lambda *args, **kwargs: None)

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, status TEXT, "
        "gh_write_verified TEXT, unpushed_branch_check_attempts INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, status, unpushed_branch_check_attempts) "
        "VALUES ('job-cap', 'done', 3)"
    )
    conn.commit()

    state = {"commits_ahead": 1, "base_commit": "base-sha"}

    result = jobs_mod._guard_unpushed_branch(
        conn, "job-cap", "done", "/tmp/missing-worktree", "fix/job-cap", state,
        "2026-10-04T09:00:00",
    )

    assert result == jobs_mod.STATUS_UNPUSHED_BRANCH
    row = conn.execute(
        "SELECT gh_write_verified, unpushed_branch_check_attempts FROM daemon_jobs WHERE job_id='job-cap'"
    ).fetchone()
    assert row == ("false", 3)
    conn.close()


def test_unpushed_guard_confirmed_push_short_circuits_regardless_of_attempts(monkeypatch):
    import sqlite3
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(jobs_mod, "local_commits_pushed", lambda *args: False)
    monkeypatch.setattr(jobs_mod, "github_branch_effect_verified", lambda *args, **kwargs: True)

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, status TEXT, "
        "gh_write_verified TEXT, unpushed_branch_check_attempts INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, status, unpushed_branch_check_attempts) "
        "VALUES ('job-confirmed', 'done', 2)"
    )
    conn.commit()

    state = {"commits_ahead": 1, "base_commit": "base-sha"}

    result = jobs_mod._guard_unpushed_branch(
        conn, "job-confirmed", "done", "/tmp/missing-worktree", "fix/job-confirmed", state,
        "2026-10-04T09:00:00",
    )

    assert result == "done"
    row = conn.execute(
        "SELECT gh_write_verified, unpushed_branch_check_attempts FROM daemon_jobs WHERE job_id='job-confirmed'"
    ).fetchone()
    assert row == (None, 2)  # unchanged — no write on the confirmed-pushed path
    conn.close()


def test_unpushed_branch_retry_pending_true_only_while_retrying_below_cap():
    import sqlite3
    import synlynk.jobs as jobs_mod

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, "
        "unpushed_branch_check_attempts INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, unpushed_branch_check_attempts) VALUES ('job-a', 1)"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, unpushed_branch_check_attempts) VALUES ('job-b', 0)"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, unpushed_branch_check_attempts) VALUES ('job-c', 3)"
    )
    conn.commit()

    # Retrying: status unchanged, attempts in (0, cap) -> pending
    assert jobs_mod._unpushed_branch_retry_pending(conn, "job-a", "done", "done") is True
    # Never retried (attempts == 0): either confirmed-pushed or guard never triggered -> not pending
    assert jobs_mod._unpushed_branch_retry_pending(conn, "job-b", "done", "done") is False
    # Cap exhausted (attempts == cap): guard already settled -> not pending
    assert jobs_mod._unpushed_branch_retry_pending(conn, "job-c", "done", "done") is False
    # Status changed (guard settled to STATUS_UNPUSHED_BRANCH) -> not pending regardless of attempts
    assert jobs_mod._unpushed_branch_retry_pending(
        conn, "job-a", "done", jobs_mod.STATUS_UNPUSHED_BRANCH
    ) is False

    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_jobs.py -k "unpushed_guard_retries or unpushed_guard_settles_unpushed_after_retry_cap or unpushed_guard_confirmed_push_short_circuits or unpushed_branch_retry_pending_true_only" -v`

Expected: `test_unpushed_guard_retries_on_inconclusive_check_instead_of_settling` FAILS (current code immediately returns `STATUS_UNPUSHED_BRANCH` and writes `gh_write_verified='false'` on the very first `None`, so `attempts` stays `0`, not `1`). `test_unpushed_branch_retry_pending_true_only_while_retrying_below_cap` FAILS with `AttributeError: module 'synlynk.jobs' has no attribute '_unpushed_branch_retry_pending'`. The other two may pass already (they match today's except-path/short-circuit behavior) — that's fine, they lock in behavior the rewrite must preserve.

- [ ] **Step 3: Add the new constant**

In `synlynk/jobs.py`, change line 37 from:

```python
_GH_WRITE_VERIFICATION_RETRY_CAP = 3
```

to:

```python
_GH_WRITE_VERIFICATION_RETRY_CAP = 3
_UNPUSHED_BRANCH_VERIFICATION_RETRY_CAP = 3
```

- [ ] **Step 4: Rewrite `_guard_unpushed_branch`**

Replace the current `_guard_unpushed_branch` (`synlynk/jobs.py:4021-4040`):

```python
def _guard_unpushed_branch(
    conn, job_id: str, status: str, worktree_path: Optional[str],
    worktree_branch: Optional[str], git_state: Optional[dict],
    started_at: Optional[str] = None,
) -> str:
    """Prevent terminal success while local commits remain off origin."""
    if not git_state or not git_state.get("commits_ahead"):
        return status
    if local_commits_pushed(worktree_path, worktree_branch, git_state.get("base_commit")):
        return status
    verified = github_branch_effect_verified(worktree_branch, since=started_at)
    if verified is True:
        return status
    if verified is None:
        try:
            attempts = int(conn.execute(
                "SELECT COALESCE(unpushed_branch_check_attempts, 0) FROM daemon_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()[0])
        except (sqlite3.OperationalError, TypeError, ValueError):
            attempts = 0
        if attempts < _UNPUSHED_BRANCH_VERIFICATION_RETRY_CAP:
            try:
                conn.execute(
                    "UPDATE daemon_jobs SET unpushed_branch_check_attempts=? WHERE job_id=?",
                    (attempts + 1, job_id),
                )
            except sqlite3.OperationalError:
                pass
            return status
    try:
        conn.execute(
            "UPDATE daemon_jobs SET gh_write_verified='false' WHERE job_id=?",
            (job_id,),
        )
    except sqlite3.OperationalError:
        pass
    return STATUS_UNPUSHED_BRANCH
```

- [ ] **Step 5: Add `_unpushed_branch_retry_pending`**

In `synlynk/jobs.py`, immediately after `_gh_write_verification_retry_pending` (which currently ends at line 3885, right before `def _load_cross_branch_pr`), insert:

```python
def _unpushed_branch_retry_pending(conn, job_id: str, pre_guard_status: str, post_guard_status: str) -> bool:
    """Return whether an inconclusive unpushed-branch check should defer terminal settlement."""
    if post_guard_status != pre_guard_status:
        return False  # guard already settled (pushed-confirmed or cap exhausted)
    try:
        attempts = conn.execute(
            "SELECT COALESCE(unpushed_branch_check_attempts, 0) FROM daemon_jobs WHERE job_id=?",
            (job_id,),
        ).fetchone()[0]
    except (sqlite3.OperationalError, TypeError, ValueError):
        return False
    return 0 < int(attempts) < _UNPUSHED_BRANCH_VERIFICATION_RETRY_CAP
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_jobs.py -k "unpushed_guard or unpushed_branch_retry_pending" -v`

Expected: all PASS, including the pre-existing `test_unpushed_guard_accepts_pr_delivery_after_head_branch_deletion`.

- [ ] **Step 7: Run the full jobs test file to check for regressions**

Run: `pytest tests/test_jobs.py -v`

Expected: all PASS (no new failures introduced — the rewritten guard still returns `status` unchanged on the confirmed-push path and the fake `conn` in `test_unpushed_guard_accepts_pr_delivery_after_head_branch_deletion` that raises `AssertionError` on any `execute` call still never gets its `execute` invoked, since `verified is True` returns before any `conn.execute`).

- [ ] **Step 8: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "feat(jobs): bounded retry for inconclusive unpushed-branch GitHub check (gh:#2136, #2137, #2130)"
```

---

### Task 3: Wire `_unpushed_branch_retry_pending` into the 3 `_reconcile_daemon_jobs` call sites

**Files:**
- Modify: `synlynk/jobs.py:4283-4289` (Site 1 — preferred-summary path)
- Modify: `synlynk/jobs.py:4386-4392` (Site 2 — zombie-reap path)
- Modify: `synlynk/jobs.py:4454-4459` (Site 3 — normal ground-truth-verification path)
- Test: `tests/test_jobs.py` (new integration tests, placed near `test_reconcile_daemon_jobs_settles_after_gh_write_unknown_retry_cap`)

- [ ] **Step 1: Write the failing tests**

Add these tests to `tests/test_jobs.py`, directly after `test_reconcile_daemon_jobs_settles_after_gh_write_unknown_retry_cap` (ends at line 2719, right before `test_apply_gh_write_verification_persists_evidence`):

```python
def test_reconcile_daemon_jobs_defers_on_inconclusive_unpushed_branch_check(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    job_id = "job-unpushed-defer"
    wt = project_dir / "worktrees" / job_id
    log = wt / ".synlynk" / "logs" / f"{job_id}.log"
    log.parent.mkdir(parents=True)
    log.write_text("agent did work\n")

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, "
        "started_at, log_path, worktree_path) VALUES "
        "(?, 'codex', 'implement thing', 'running', 999999, "
        "'2026-10-04T09:00:00', '2026-10-04T09:00:00', ?, ?)",
        (job_id, str(log), str(wt)),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(
        jobs_mod, "_existing_terminal_summary_truth", lambda job_id: ("done", 0),
    )
    monkeypatch.setattr(
        jobs_mod, "_worktree_git_state_inspector",
        lambda: lambda path, branch=None, started_at=None: {
            "has_activity": True, "commits_ahead": 1, "base_commit": "base-sha", "dirty": False,
        },
    )
    monkeypatch.setattr(jobs_mod, "local_commits_pushed", lambda *a, **k: False)
    monkeypatch.setattr(jobs_mod, "github_branch_effect_verified", lambda *a, **k: None)

    jobs_mod._reconcile_daemon_jobs()

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status, unpushed_branch_check_attempts FROM daemon_jobs WHERE job_id=?",
        (job_id,),
    ).fetchone()
    conn.close()
    # Deferred, not settled: status must still read as the pre-terminal "running"
    # row (daemon never committed an unpushed_branch/done terminal write), and the
    # attempt counter must have advanced exactly once.
    assert row == ("running", 1)


def test_reconcile_daemon_jobs_settles_unpushed_branch_after_retry_cap(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    job_id = "job-unpushed-cap"
    wt = project_dir / "worktrees" / job_id
    log = wt / ".synlynk" / "logs" / f"{job_id}.log"
    log.parent.mkdir(parents=True)
    log.write_text("agent did work\n")

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, "
        "started_at, log_path, worktree_path, unpushed_branch_check_attempts) VALUES "
        "(?, 'codex', 'implement thing', 'running', 999999, "
        "'2026-10-04T09:00:00', '2026-10-04T09:00:00', ?, ?, 3)",
        (job_id, str(log), str(wt)),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(
        jobs_mod, "_existing_terminal_summary_truth", lambda job_id: ("done", 0),
    )
    monkeypatch.setattr(
        jobs_mod, "_worktree_git_state_inspector",
        lambda: lambda path, branch=None, started_at=None: {
            "has_activity": True, "commits_ahead": 1, "base_commit": "base-sha", "dirty": False,
        },
    )
    monkeypatch.setattr(jobs_mod, "local_commits_pushed", lambda *a, **k: False)
    monkeypatch.setattr(jobs_mod, "github_branch_effect_verified", lambda *a, **k: None)

    jobs_mod._reconcile_daemon_jobs()

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status, gh_write_verified, unpushed_branch_check_attempts FROM daemon_jobs WHERE job_id=?",
        (job_id,),
    ).fetchone()
    conn.close()
    assert row == (jobs_mod.STATUS_UNPUSHED_BRANCH, "false", 3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_jobs.py -k "defers_on_inconclusive_unpushed_branch or settles_unpushed_branch_after_retry_cap" -v`

Expected: `test_reconcile_daemon_jobs_defers_on_inconclusive_unpushed_branch_check` FAILS — with today's code, the call site has no retry-pending check after `_guard_unpushed_branch`, so the job settles to `unpushed_branch` on the very first inconclusive check instead of deferring; `attempts` stays `0` and `status` becomes `unpushed_branch` instead of staying `running`.

- [ ] **Step 3: Wire Site 1 (preferred-summary path, `jobs.py:4283-4289`)**

Replace:

```python
                    status = _guard_unpushed_branch(
                        conn, job_id, status, preferred_path, preferred_branch, preferred_state,
                        started_at,
                    )
                    status, exit_code, _merged_note = _promote_merged_pr_result(
                        status, exit_code, preferred_branch, started_at
                    )
```

with:

```python
                    pre_guard_status = status
                    status = _guard_unpushed_branch(
                        conn, job_id, status, preferred_path, preferred_branch, preferred_state,
                        started_at,
                    )
                    if _unpushed_branch_retry_pending(conn, job_id, pre_guard_status, status):
                        conn.commit()
                        continue
                    status, exit_code, _merged_note = _promote_merged_pr_result(
                        status, exit_code, preferred_branch, started_at
                    )
```

- [ ] **Step 4: Wire Site 2 (zombie-reap path, `jobs.py:4386-4392`)**

Replace:

```python
                        zombie_status = _guard_unpushed_branch(
                            conn, job_id, zombie_status, worktree_path, worktree_branch, git_state,
                            started_at,
                        )
                        zombie_status, zombie_exit_code, _merged_note = _promote_merged_pr_result(
                            zombie_status, zombie_exit_code, worktree_branch, started_at
                        )
```

with:

```python
                        pre_guard_zombie_status = zombie_status
                        zombie_status = _guard_unpushed_branch(
                            conn, job_id, zombie_status, worktree_path, worktree_branch, git_state,
                            started_at,
                        )
                        if _unpushed_branch_retry_pending(
                            conn, job_id, pre_guard_zombie_status, zombie_status
                        ):
                            _release_daemon_job_terminal_claim_and_commit(
                                conn, job_id, terminal_claim_token
                            )
                            continue
                        zombie_status, zombie_exit_code, _merged_note = _promote_merged_pr_result(
                            zombie_status, zombie_exit_code, worktree_branch, started_at
                        )
```

This mirrors the existing `_gh_write_verification_retry_pending` defer a few lines below at this same site (`jobs.py:4400-4406`), which also releases the terminal claim via `_release_daemon_job_terminal_claim_and_commit` rather than a bare `conn.commit()` — this branch is inside the `try` that holds `terminal_claim_token` from `_claim_daemon_job_terminal`.

- [ ] **Step 5: Wire Site 3 (normal ground-truth-verification path, `jobs.py:4454-4459`)**

Replace:

```python
                status = _guard_unpushed_branch(
                    conn, job_id, status, worktree_path, worktree_branch, git_state, started_at
                )
                status, exit_code, merged_note = _promote_merged_pr_result(
                    status, exit_code, worktree_branch, started_at
                )
```

with:

```python
                pre_guard_status = status
                status = _guard_unpushed_branch(
                    conn, job_id, status, worktree_path, worktree_branch, git_state, started_at
                )
                if _unpushed_branch_retry_pending(conn, job_id, pre_guard_status, status):
                    conn.commit()
                    continue
                status, exit_code, merged_note = _promote_merged_pr_result(
                    status, exit_code, worktree_branch, started_at
                )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_jobs.py -k "defers_on_inconclusive_unpushed_branch or settles_unpushed_branch_after_retry_cap" -v`

Expected: both PASS.

- [ ] **Step 7: Run the full test suite**

Run: `pytest tests/ -v`

Expected: all PASS, no regressions. Pay particular attention to any existing zombie-reap tests (search `pytest tests/test_jobs.py -k zombie -v` if the full run is slow) since Site 2's edit touches the `terminal_claim_token` release path.

- [ ] **Step 8: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "fix(jobs): defer terminal settlement on inconclusive unpushed-branch check at all 3 call sites (gh:#2136, #2137, #2130)"
```

---

## Self-Review

**Spec coverage:**
- §1 New column → Task 1. ✅
- §2 New retry cap constant → Task 2 Step 3. ✅
- §3 Three-outcome `_guard_unpushed_branch` → Task 2 Step 4. ✅
- §4 New `_unpushed_branch_retry_pending` + 3 call sites → Task 2 Step 5 + Task 3. ✅ (Task 3 additionally corrects the spec's assumption of a uniform commit idiom — see the "Important implementation note" above — without changing the spec's actual retry/cap semantics.)
- §5 No oracle involvement → satisfied; no task touches `job_truth.py`.
- Testing section's 6 bullets → covered: attempts increment 1→2→3 (Task 2 test 1), cap-exhaustion downgrade (Task 2 test 2), `True`-short-circuits-at-any-attempts (Task 2 test 3), `_unpushed_branch_retry_pending` behavior (Task 2 test 4), job-26b6196d-shaped regression at the full-reconciliation level (Task 3 tests 1–2, which together show inconclusive→defer→(eventually, once a later poll confirms or cap exhausts)→settle correctly, exercised through `_reconcile_daemon_jobs` itself rather than the guard function in isolation), existing daemon-reconciliation tests re-run with no regression (Task 3 Step 7).

**Placeholder scan:** No TBD/TODO. All code blocks are complete, copy-pasteable. No "similar to Task N" references — Task 3's three call-site edits are each written out in full despite being structurally similar, since the zombie-reap site's commit idiom genuinely differs.

**Type consistency:** `_guard_unpushed_branch`'s signature (`conn, job_id, status, worktree_path, worktree_branch, git_state, started_at`) is unchanged from the existing function — Task 2 Step 4 only changes its body. `_unpushed_branch_retry_pending(conn, job_id, pre_guard_status, post_guard_status) -> bool` is used identically in Task 2's tests and all 3 Task 3 call sites. `STATUS_UNPUSHED_BRANCH` is the existing module constant (`jobs.py:69`), referenced consistently.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-10-unpushed-branch-verification-retry.md`.

**Per this project's Default Agent Role policy (CLAUDE.md), implementation should be dispatched via `synlynk dispatch` to Agy/Grok/Codex rather than written directly by Claude** — Claude's role is PM/review/deploy. This is a backend-only, no-new-dependency change (pure stdlib `sqlite3` patterns already used throughout `jobs.py`), and all 3 tasks are tightly coupled (the call-site wiring in Task 3 depends on the exact helper/constant from Task 2, which depends on the column from Task 1) — **a single dispatched implementer job covering all 3 tasks is the right scope**, not 3 separate dispatches.

Two execution options:

**1. Subagent-Driven (recommended)** — dispatch via `synlynk dispatch` to an implementer harness (Codex/Grok per the GitHub-write-routing table, or Agy), with review between tasks.

**2. Inline Execution** — execute tasks in this session using `executing-plans`, batch execution with checkpoints (would require an explicit exception to the Default Agent Role policy — flag this to the user if chosen).

Which approach?
