# `_reconcile_terminal_jobs_json` Retry-Gate Wiring — Design Spec

**Fixes:** the job-status false-negative Cluster A family — gh:#2137, gh:#2138, gh:#2139, gh:#2163 — specifically the instance of the bug class that fires on the `jobs.json`→`daemon_jobs` CLI bridge path rather than the daemon's main poll loop.

**Governs:** story-25872226 / goal-bde24050.

## Context: why this spec exists, and what it is not

The 2026-10-10 decide panel (`project-docs/decisions/2026-10-10-the-job-status-false-negative-gh-write-v.md`, `dec-39b77de7`) considered two approaches for the job-status split-brain cluster:

- **Approach 1** (rejected): add a retry-cap patch directly inside the terminal-settlement path, written as a new ad hoc fix.
- **Approach 2** (destination, not yet promoted): promote the existing shadow oracle (`job_truth.py` / `job_status_projection.py`) from shadow to authoritative, gated behind `SYNLYNK_JOB_TRUTH_MODE`.

The panel's synthesis: treat Approach 2 as the eventual architecture, but **do not promote it yet** — ship a narrow, non-terminal stopgap now instead, one that adds no second terminal-status writer (which would recreate the exact split-brain the oracle exists to resolve).

**Data pull done before writing this spec, per the panel's own instruction:** `job_truth_metrics()` + `promotion_gate()` were run against the canonical `state.db` (`~/.synlynk/workspaces/synlynk/state.db`, 288MB; `job_status_shadow` has 362 rows, above the 100-sample minimum). Result: **`eligible: false`, failing 4 of 8 SLOs**:

| SLO | Required | Measured |
|---|---|---|
| `no_missing_contract` | 0 `unknown_contract` rows | 2,206 |
| `verification_age_slo` | max unknown-age ≤ 300s | ~656,745s (~7.6 days) |
| `unknown_verifying_slo` | max 0 stuck jobs | 443 |
| `harness_effect_agreement` | disagreement within allowlist | 362/362 samples disagree (100%) — reason codes `legacy_status_unmapped` (186), `status_disagreement` (176); **zero** `false_failure`/`false_success` |

This confirms oracle promotion is far from ready, and that the oracle's `decide_job_outcome` returning `unknown_contract` before inspecting evidence (Cluster D) is pathological at the scale actually running, not an edge case. **Oracle promotion and Cluster D's `contract_missing` remediation are explicitly out of scope for this spec** — tracked separately, gated on today's measured baseline above.

**This spec covers only the narrowest slice of Cluster A**: a specific code path, described below, that is missing retry-deferral logic other code paths already have.

### A wasted dispatch this spec corrects course from

Before this spec, job-f2a52851 was dispatched to implement the rejected Approach 1 retry-cap pattern against the wrong target. It cost $5.03 / 1.65M tokens, finished `SCOPE_REVIEW_REQUIRED`/`unknown_contract`, and produced zero file changes (confirmed via `git diff origin/main --stat` and two independent `gh pr list` searches — no PR exists). Logged as a cost-inflation data point on gh:#2121; the mischaracterization corrected via comment on gh:#2137. Nothing from that dispatch landed, so there is nothing to revert.

## Problem

`_reconcile_terminal_jobs_json` (`synlynk/jobs.py:3713-3783`) is the bridge that applies terminal events recorded in the legacy `jobs.json` flat file to still-`running` rows in the `daemon_jobs` SQL table. Its docstring states the reason it exists: a dispatched process can write its terminal flat-file record before the daemon's own poll loop gets to update SQLite, so without this bridge the SQL row stays `running` forever. It runs synchronously on every invocation of `_reconcile_daemon_jobs`, which calls it at `jobs.py:4326` (confirmed via `grep -n "_reconcile_terminal_jobs_json(" synlynk/jobs.py` — the function has exactly one production call site, inside `_reconcile_daemon_jobs`, not `_reconcile_jobs_unlocked`), which makes it, in practice, often the *only* settlement attempt a CLI-dispatched job ever gets.

The daemon's own main poll loop (`_reconcile_daemon_jobs`) already has two retry-deferral gates that exist precisely to avoid committing a bad terminal status from an inconclusive check:

1. **`_gh_write_verification_retry_pending`** (`jobs.py:4020-4033`) — if a `requires_gh_write` job's GitHub-effect check comes back `"unknown"` and the job hasn't exhausted `_GH_WRITE_VERIFICATION_RETRY_CAP` attempts, defer settlement (leave the row `running`) instead of locking in a best-guess status.
2. **`_unpushed_branch_retry_pending`** (`jobs.py:4036-4047`) — the equivalent gate for `_guard_unpushed_branch`'s inconclusive-GitHub-check case (shipped by the prior `2026-10-10-unpushed-branch-verification-retry-design.md` spec).

The main poll loop calls both gates, at three call sites (`jobs.py:4468`/`4481`, `4575`/`4592`, `4650`/`4665`), each time checking `_unpushed_branch_retry_pending` and `_gh_write_verification_retry_pending` and `continue`-ing (skipping settlement, leaving the row `running`) whenever either signals "still retrying."

**`_reconcile_terminal_jobs_json` calls neither gate, and never calls `_guard_unpushed_branch` at all.** Its current body:

```python
row = conn.execute(
    "SELECT requires_gh_write, gh_write_target, gh_write_author, gh_write_expect "
    "FROM daemon_jobs WHERE job_id=? AND status='running'",
    (job_id,),
).fetchone()
if not row:
    continue
requires_gh_write, target, author, expect = row
if requires_gh_write:
    status, verified = _verify_daemon_terminal_status(
        conn, job_id, requires_gh_write, target or job.get("gh_write_target"),
        status, job.get("started_at"), author or job.get("gh_write_author"),
        expect or job.get("gh_write_expect"), worktree_branch=job.get("worktree_branch"),
    )
else:
    verified = None
exit_code = job.get("exit_code")
completed_at = job.get("ended_at") or time.strftime("%Y-%m-%dT%H:%M:%S")
if _settle_daemon_job_terminal(
    conn, job_id, status, exit_code, completed_at, only_running=True
):
    repaired += 1
    ...
```

It calls `_verify_daemon_terminal_status` for GH-write jobs, but then calls `_settle_daemon_job_terminal` **unconditionally** regardless of whether `verified` came back `"unknown"`. And it never calls `_guard_unpushed_branch` at all, so a job whose local commits are genuinely unpushed (and whose GitHub-merge check is momentarily inconclusive) gets no protection whatsoever on this path — only on the main poll loop's path, which this bridge frequently preempts.

Net effect: both existing, already-tested retry-deferral mechanisms are bypassed on a code path that is often the only settlement attempt a job gets. This is a strict subset of Cluster A — it does not touch the oracle, `job_truth.py`, or any new status value.

## Fix

Mirror the main poll loop's exact pattern inside `_reconcile_terminal_jobs_json`. No new column, no new status value, no new terminal writer — every primitive used here already exists and is already proven (`_guard_unpushed_branch`, `_unpushed_branch_retry_pending`, `_verify_daemon_terminal_status`, `_gh_write_verification_retry_pending`, `_worktree_git_state_inspector`, `_daemon_job_worktree_path` all already ship).

### 1. Extend the per-job SELECT

Current (`jobs.py:3743-3747`):
```python
row = conn.execute(
    "SELECT requires_gh_write, gh_write_target, gh_write_author, gh_write_expect "
    "FROM daemon_jobs WHERE job_id=? AND status='running'",
    (job_id,),
).fetchone()
```

New — add the two columns the main loop's own SELECT already reads at `jobs.py:4339`:
```python
row = conn.execute(
    "SELECT requires_gh_write, gh_write_target, gh_write_author, gh_write_expect, "
    "worktree_path, worktree_branch "
    "FROM daemon_jobs WHERE job_id=? AND status='running'",
    (job_id,),
).fetchone()
if not row:
    continue
requires_gh_write, target, author, expect, worktree_path, worktree_branch = row
```

### 2. Insert the unpushed-branch guard before the existing GH-write check

```python
preferred_path = worktree_path or _daemon_job_worktree_path(job_id, job.get("log_path"))
preferred_branch = worktree_branch or job.get("worktree_branch")
preferred_state = None
if preferred_path:
    try:
        preferred_state = _worktree_git_state_inspector()(
            preferred_path, preferred_branch, job.get("started_at")
        )
    except Exception:
        preferred_state = None
pre_guard_status = status
status = _guard_unpushed_branch(
    conn, job_id, status, preferred_path, preferred_branch, preferred_state,
    job.get("started_at"),
)
if _unpushed_branch_retry_pending(conn, job_id, pre_guard_status, status):
    conn.commit()
    continue
```

`continue` here advances to the next `job_id` in the `for job_id, (job, status) in terminal_jobs.items():` loop — this function is a one-shot dict iteration, not a persistent poll loop, so "deferring" means: this invocation of `_reconcile_terminal_jobs_json` leaves the row `running` and does not count it in `repaired`; the next CLI invocation that reconciles jobs will re-attempt the same job from the top (same semantics as the main poll loop deferring to its next cycle).

`worktree_path`/`worktree_branch` from the SQL row are preferred over `job.get("worktree_branch")` from the `jobs.json` record, matching the main loop's `persisted_worktree_path or ...` precedence (`jobs.py:4356-4357`) — the SQL columns are the more authoritative, more recently-written source when both exist.

### 3. Gate the existing GH-write verification the same way

The existing `if requires_gh_write:` block already calls `_verify_daemon_terminal_status`. Add the missing retry check immediately after it, before falling through to settlement:

```python
if requires_gh_write:
    status, verified = _verify_daemon_terminal_status(
        conn, job_id, requires_gh_write, target or job.get("gh_write_target"),
        status, job.get("started_at"), author or job.get("gh_write_author"),
        expect or job.get("gh_write_expect"), worktree_branch=preferred_branch,
    )
    if _gh_write_verification_retry_pending(conn, job_id, requires_gh_write, verified):
        conn.commit()
        continue
else:
    verified = None
```

(`worktree_branch=preferred_branch` replaces the old `worktree_branch=job.get("worktree_branch")` — using the same resolved value computed in step 2, consistent with the main loop passing `preferred_branch` at its equivalent call, `jobs.py:4479`.)

### 4. Settlement is unchanged

`_settle_daemon_job_terminal(..., only_running=True)` only runs for jobs that passed both gates (or had neither condition apply), exactly as today — this spec adds no new call to it and no new terminal status value.

## Explicitly out of scope

- Oracle promotion (`SYNLYNK_JOB_TRUTH_MODE`) — blocked on the measured promotion-gate failure above; tracked separately.
- Cluster D's `decide_job_outcome`/`unknown_contract`-before-evidence remediation — tracked separately, not touched by this fix.
- Any change to `_guard_unpushed_branch`'s or `_verify_daemon_terminal_status`'s own internal retry/cap logic — both already shipped correctly via the prior `2026-10-10-unpushed-branch-verification-retry-design.md` spec and an earlier GH-write verification fix; this spec only reaches code that already exists.
- Any change to the main poll loop (`_reconcile_daemon_jobs`) itself — it already has both gates wired correctly; this spec brings the bridge function up to the same standard.

## Testing

- Unit test: a `daemon_jobs` row with `requires_gh_write=1`, mocked `_verify_daemon_terminal_status` returning `"unknown"` — assert `_reconcile_terminal_jobs_json` leaves the row `status='running'` (not settled), returns a `repaired` count that excludes this job, and does not emit a `job_terminal` event for it.
- Unit test: same job, second call with the mock now returning `"true"`/`"false"` (verification resolved) — assert the row settles terminally and `repaired` includes it.
- Unit test: a job with real local-only commits (`git_state.commits_ahead` truthy, `local_commits_pushed` false) and `github_branch_effect_verified` mocked to return `None` — assert the bridge leaves the row `running` and increments `unpushed_branch_check_attempts`, mirroring the main loop's already-tested behavior for the same mock.
- Unit test: same setup, but `unpushed_branch_check_attempts` already at `_UNPUSHED_BRANCH_VERIFICATION_RETRY_CAP` — assert the bridge now settles the job as `STATUS_UNPUSHED_BRANCH` (cap-exhausted fallback), matching the main loop's behavior.
- Regression test: reproduce the job-26b6196d shape (real merge, momentarily inconclusive GitHub check) specifically via the CLI-bridge path (i.e. drive `_reconcile_terminal_jobs_json` directly, not `_reconcile_daemon_jobs`) — assert it no longer locks in `unpushed_branch` on the first inconclusive check.
- Existing tests covering `_reconcile_terminal_jobs_json`'s current behavior (`only_running=True` idempotency, non-GH-write jobs, already-terminal rows being skipped) re-run to confirm no regression.

## Acceptance

- `_reconcile_terminal_jobs_json` defers settlement (row stays `running`, job excluded from `repaired` count, no `job_terminal` event emitted) whenever either `_unpushed_branch_retry_pending` or `_gh_write_verification_retry_pending` signals true, exactly mirroring the main poll loop's behavior for the same inputs.
- No new `daemon_jobs` column, no new status value, no new terminal writer.
- All existing tests for `_reconcile_terminal_jobs_json`, `_reconcile_daemon_jobs`, `_guard_unpushed_branch`, and `_verify_daemon_terminal_status` continue to pass unmodified.
