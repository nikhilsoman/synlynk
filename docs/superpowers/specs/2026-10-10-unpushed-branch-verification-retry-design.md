# `_guard_unpushed_branch` Inconclusive-Verification Retry — Design Spec

**Fixes:** gh:#2136 (sev1,p0 — no bounded retry before permanent terminal settle), gh:#2137 (sev1,p0 — race between per-CLI classification and daemon-poll GH verification), and the gh:#2130 false-negative class (job-26b6196d: a real merge misclassified as `unpushed_branch`).

Root-caused via `superpowers:systematic-debugging`; findings posted as a GitHub comment on gh:#2137. This spec covers **Bug A only**. Bug B (`job_truth.py`'s `unknown_contract` trap, gh:#2158/#2138) is a separate, independent latent bug in the still-shadow-mode oracle and is explicitly out of scope here — it gets its own spec.

## Problem

`_guard_unpushed_branch` (`synlynk/jobs.py:4021`) is the daemon's guard against declaring a job terminal-successful while its commits are only local. When `local_commits_pushed()` says no, it falls back to asking GitHub directly via `github_branch_effect_verified()` (`synlynk/gh_verify.py:62`, a single `gh pr list --head <branch> ...` call):

```python
if github_branch_effect_verified(worktree_branch, since=started_at) is True:
    return status
# falls through unconditionally otherwise
conn.execute("UPDATE daemon_jobs SET gh_write_verified='false' WHERE job_id=?", (job_id,))
return STATUS_UNPUSHED_BRANCH
```

`github_branch_effect_verified` returns `None` — not `False` — whenever the check is genuinely inconclusive: a subprocess timeout/`OSError`, a non-zero `gh` exit, or unparseable JSON. The `is True` check above treats `None` (unknown) and `False` (confirmed not merged) identically. Any transient `gh` hiccup — rate limiting, a momentary auth blip, a slow API response — gets silently collapsed into "confirmed unpushed" and committed as a terminal `STATUS_UNPUSHED_BRANCH`, with **zero retry**.

This is the literal shape of job-26b6196d: a job that had, in fact, been merged, hit an inconclusive GitHub check at verification time and was permanently misclassified.

Contrast this with `_apply_gh_write_verification` (`synlynk/jobs.py:3812`), the function immediately adjacent in the same reconciliation flow, which verifies a *different* GH-write condition (PR/issue/review effect) and already has exactly the missing machinery:
- A persisted per-job attempt counter (`daemon_jobs.gh_write_verification_attempts`)
- A retry cap (`_GH_WRITE_VERIFICATION_RETRY_CAP = 3`)
- A companion `_gh_write_verification_retry_pending()` check that defers terminal settlement (`conn.commit(); continue`) instead of committing on an inconclusive result
- At cap, it gives up *without forcing a failure* — it returns the original status unchanged, marking verification `"unknown"` rather than asserting `"false"`

`_guard_unpushed_branch` never received the same treatment. This spec applies the identical, already-proven pattern to it.

## Fix

### 1. New column

`daemon_jobs.unpushed_branch_check_attempts INTEGER NOT NULL DEFAULT 0`

Added via the project's existing idempotent migration idiom in `synlynk/db.py`, in the same block as the other `daemon_jobs` column additions (near `gh_write_verification_attempts`, `db.py:1302-1309`):

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

### 2. New retry cap constant

`_UNPUSHED_BRANCH_VERIFICATION_RETRY_CAP = 3` (separate constant from `_GH_WRITE_VERIFICATION_RETRY_CAP`, same value, kept distinct because the two checks verify unrelated conditions and may need independent tuning later).

### 3. `_guard_unpushed_branch` distinguishes three outcomes instead of two

Current behavior collapses to two outcomes (pushed / not-pushed-or-unknown). New behavior:

- **`True`** (GitHub confirms pushed/merged) — unchanged: return original `status`.
- **`False`** (today's unconditional fallthrough no longer applies here — see below) — only reachable once `github_branch_effect_verified` returns `None` repeatedly up through the cap, or in a future version of `gh_verify.py` that returns an explicit `False`. Today the function cannot distinguish "confirmed not merged" from "inconclusive" at the `gh_verify.py` layer (it returns `None` for both not-found-and-no-error and for actual errors) — this spec does not change `gh_verify.py`'s return contract, only how `_guard_unpushed_branch` consumes `None`.
- **`None`** (inconclusive) — read `unpushed_branch_check_attempts` for this job. If `attempts < _UNPUSHED_BRANCH_VERIFICATION_RETRY_CAP`: increment and persist the counter, return the **original** `status` unchanged (do not downgrade yet). If `attempts >= cap`: commit `STATUS_UNPUSHED_BRANCH` (today's existing fallback behavior, now reached only after exhausting retries instead of immediately).

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

### 4. New `_unpushed_branch_retry_pending()` helper, called at all 3 sites

Structurally identical to `_gh_write_verification_retry_pending` (`jobs.py:3872`). The signal for "still retrying" vs. "settled" cannot be the status value alone — "unchanged because pushed-confirmed" and "unchanged because still retrying" produce the same status. Instead, use the fact that only the retrying path increments `unpushed_branch_check_attempts`: a nonzero attempts count below the cap means the previous call deferred rather than settled.

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

Call sites pass the status captured immediately before and after invoking `_guard_unpushed_branch`:

```python
pre_guard_status = status
status = _guard_unpushed_branch(
    conn, job_id, status, preferred_path, preferred_branch, preferred_state, started_at,
)
if _unpushed_branch_retry_pending(conn, job_id, pre_guard_status, status):
    conn.commit()
    continue
status, exit_code, _merged_note = _promote_merged_pr_result(status, exit_code, preferred_branch, started_at)
```

This mirrors the existing `_gh_write_verification_retry_pending()` call pattern two statements later in the same function at all 3 sites (`jobs.py:4283`, `4386`, `4454`).

### 5. No oracle involvement

This fix is entirely contained to `synlynk/jobs.py` and `synlynk/gh_verify.py`'s existing legacy heuristic layer. `job_truth.py`'s shadow-mode oracle rollout is untouched — no coupling, no new risk to that separate, independently-paced effort.

## Explicitly out of scope

- `_promote_merged_pr_result`'s correction set (`jobs.py:4043`) does not include `STATUS_UNPUSHED_BRANCH` among the statuses it can retroactively correct via a confirmed-merged-PR check. This is a related but separate gap — worth a follow-up issue, not folded into this fix, to keep this change isolated and independently testable.
- Bug B (`job_truth.py` `unknown_contract` trap) — separate spec.
- Changing `gh_verify.py`'s `github_branch_effect_verified` return contract (e.g., adding a true three-state `True`/`False`/`None` distinction at the API level) — not needed for this fix; the retry/cap logic is added at the `_guard_unpushed_branch` call site instead.

## Testing

- Unit test: `github_branch_effect_verified` mocked to return `None` on first 3 calls — assert `_guard_unpushed_branch` returns the original (unchanged) status each time and `unpushed_branch_check_attempts` increments 1→2→3.
- Unit test: same mock returning `None` on a 4th call after attempts already at cap — assert the function now returns `STATUS_UNPUSHED_BRANCH` and sets `gh_write_verified='false'`.
- Unit test: mock returning `True` at any attempt count (including after prior `None`s) — assert immediate return of the original status, no further column writes.
- Unit test: `_unpushed_branch_retry_pending()` — assert `True` only when post-guard status is unchanged from pre-guard AND attempts is in `(0, cap)`; `False` once cap is reached or status changed.
- Regression test reproducing job-26b6196d's shape: inconclusive check, then (on a later poll cycle) a confirmed push — assert the job settles correctly as pushed/merged rather than `unpushed_branch`.
- Existing daemon-reconciliation tests covering the 3 call sites (`jobs --all` zombie reap, normal terminal settle, preferred-summary path) re-run to confirm no regression in the already-passing paths.
