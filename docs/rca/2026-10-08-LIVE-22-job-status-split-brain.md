# [LIVE-22] Job-status false negatives: jobs.json / daemon_jobs split-brain never self-heals

- **Severity:** Sev1 — core product telemetry (`synlynk jobs --all`, dispatch status labels) is
  wrong in a way that is visible to every user of every dispatched job, and the wrong verdict
  persists indefinitely with no self-correction.
- **Issue:** gh:#2130
- **Date:** 2026-10-08
- **Status:** Root-caused. No code fix shipped yet (this doc is the Declare/Investigate output per
  the Live Issues SOP; action tickets below still need to be filed/dispatched).

## Timeline

- Across this session, well over a dozen dispatched jobs (Codex, Grok, and Agy; review, implement,
  and infra task types) reported a terminal status via `synlynk jobs --all` that did **not** match
  the job's actual, verified GitHub effect, confirmed independently via direct `gh pr view` /
  `gh issue view` calls. In every case checked, the mismatch did not self-correct over the following
  hours — the only way to learn the true state was to bypass synlynk's own status surface entirely.
- 2026-10-09 (session, this investigation): re-read `docs/rca/2026-09-09-ISSUE-1531-dispatch-token-inflation.md`,
  which diagnosed the same symptom a month earlier and prescribed an "evidence union" fix (a verified
  GitHub effect should downgrade a missing/late task receipt from a hard fail to a warning).
- Confirmed via direct code reading that the ISSUE-1531 P1 fix **was implemented**:
  `_classify_task_delivery` / `_job_has_verified_gh_write_evidence` /
  `_task_delivery_has_corroborating_activity` (`synlynk/jobs.py:481-568`) exist and do exactly what
  that RCA asked for — so the recurring failures are not "the fix was never built."
- Traced the actual data flow end to end (see Root Cause) and found a second, deeper architectural
  gap that the evidence-union fix sits on top of but cannot route around: a one-way, single-attempt
  sync between two separate job-status stores, with no retry on a transient verification failure.

## Root Cause

synlynk has **two job-status stores that are reconciled by two different code paths running at two
different cadences**, and the handoff between them is a single, non-retrying, one-way copy:

1. **`.synlynk/jobs.json`** (flat file). Written by `_reconcile_jobs_unlocked()`
   (`synlynk/jobs.py:2014-2647`), whose own docstring says it is "called on every synlynk invocation
   before any command runs." It classifies a just-exited process using only cheap, local evidence —
   log text (receipt markers) and git worktree state (`_inspect_worktree_git_state`). It never makes a
   live GitHub API call. This is the path that sets `task_delivery_failed` and similar terminal
   statuses the moment a process exits, using whatever (possibly empty) `gh_write_verified` value is
   already cached on the in-memory job record.

2. **`daemon_jobs`** (SQL table in `state.db`). This is the store `synlynk jobs --all` actually reads
   (`cmd_jobs`, `synlynk/jobs.py:4607`, docstring: "Prints jobs from daemon_jobs in state.db").
   It is reconciled only by the background daemon's poll loop, via `_reconcile_daemon_jobs()`
   (`synlynk/jobs.py:3997`), called from `synlynk/daemon.py:1115` and `:1322` — **not** from the
   per-CLI path above.

The only bridge between the two is `_reconcile_terminal_jobs_json(conn)` (`synlynk/jobs.py:3471`),
called exactly once per daemon poll tick from inside `_reconcile_daemon_jobs()` (line 4019). Its own
docstring is explicit about what it is: *"`jobs.json` is a legacy event/projection store, while
`daemon_jobs` is the store used by `synlynk jobs`. ... Treat terminal flat-file records as idempotent
terminal events: update only rows still marked running, and never overwrite an already terminal
SQLite result."*

That last clause is the actual root cause. Walking the code:

- `_reconcile_terminal_jobs_json` only acts on a `daemon_jobs` row when
  `SELECT ... FROM daemon_jobs WHERE job_id=? AND status='running'` finds a match
  (`synlynk/jobs.py:3498-3502`). If the row is already terminal for any other reason, this function
  is a silent no-op for that job — forever. There is no scheduled or triggered re-check.
- When it does fire and the job `requires_gh_write`, it calls `_verify_daemon_terminal_status`
  (`:3816`) → `_apply_gh_write_verification` (`:3714`) to do the one and only real, live GitHub check
  this job will ever receive. If `gh_write_verified(...)` raises (network blip, transient auth/rate
  limit, any `Exception`), the function catches it, prints a warning to stderr, and sets
  `verified = None` → `verified_str = "unknown"` (`:3714-3730`). Critically, the status-override logic
  only fires `if verified is False` (flips to `succeeded_gh_write_failed`) — on `None`/`"unknown"` the
  pre-existing status (whatever `.synlynk/jobs.json`'s cheap local classification produced, e.g.
  `task_delivery_failed`) passes through **unchanged**.
- That result is then persisted via `_settle_daemon_job_terminal(..., only_running=True)` →
  `_persist_daemon_job_terminal(..., only_running=True)` (`:2701-2752`), which — by design — only ever
  transitions a row out of `running`, once. Nothing in the codebase re-opens an already-terminal
  `daemon_jobs` row for a second verification attempt. The only escape hatch is the manual
  `cmd_jobs_reconcile_truth` command (`:4853`), an operator-invoked override.

Put together: **a job gets exactly one shot at real GitHub verification, at a daemon-poll-cadence
timing that races the per-CLI jobs.json classification, and if that one shot hits any transient
failure (or simply never runs because the row already left `running` some other way), the wrong
verdict is permanent.** This fully explains both halves of the observed symptom: (a) the status is
often wrong immediately after a job finishes (the per-CLI path runs first, using only local evidence,
and the user's very next `synlynk jobs --all` reads whatever `daemon_jobs` already had before the
daemon's next poll tick), and (b) it stays wrong for hours (once `_settle_daemon_job_terminal` has
run once, there is no retry, verified-fix or not).

The evidence-union fix from ISSUE-1531 is real and does help the cases where `gh_write_verified`
happens to already be populated before `_reconcile_jobs_unlocked` runs. It does not help the much
larger set of cases where the real verification simply hasn't had its one allotted attempt yet, or
that attempt failed transiently — which is the majority of what was observed this session.

## Why useful work was repeatedly marked failed

Every mislabeled job this session shared the same shape: the job's actual GitHub side effect (a
review, a merge, a comment) was genuine and correct, but `synlynk jobs --all` reported a failure-like
terminal status that was set by the cheap, local-evidence-only path before (or instead of) the one
real verification attempt ever ran to completion successfully. None of the harnesses (Codex, Grok,
Agy) behaved differently from each other — the defect is in synlynk's own status-classification
plumbing, not in any dispatched agent's behavior.

## Affected components

- `synlynk/jobs.py`: `_reconcile_jobs_unlocked`, `_reconcile_terminal_jobs_json`,
  `_reconcile_daemon_jobs`, `_verify_daemon_terminal_status`, `_apply_gh_write_verification`,
  `_settle_daemon_job_terminal`, `_persist_daemon_job_terminal`, `cmd_jobs`.
- `synlynk/daemon.py`: poll-loop call sites at `:1115` and `:1322` (cadence of the only path that can
  ever correct a wrong verdict).
- Every dispatch consumer that trusts `synlynk jobs --all` / status labels as ground truth without
  independent `gh` verification — i.e., every prior session memory entry warning "never trust
  `synlynk jobs` status alone" was a correct, recurring workaround for this exact defect.

## Impact

- Systemic erosion of trust in synlynk's own job-status telemetry: this session alone logged well
  over a dozen false-negative occurrences across 3 harnesses and multiple task types, each requiring
  a manual `gh` round-trip to disprove.
- Downstream cost: at least one dispatch was re-run (and re-billed) purely because its status label
  looked like failure when the underlying work had already succeeded.
- Masks real failures too: because operators have learned to distrust the label and always
  double-check, a *genuine* failure buried among false negatives is easy to under-react to.

## Prioritized remediation

- **P0 — stop the one-shot verification from being permanent.** Add a bounded retry: when
  `_apply_gh_write_verification` returns `"unknown"` (verification raised or was inconclusive) for a
  `requires_gh_write` job, do not settle the `daemon_jobs` row as terminal. Leave it `running` (or a
  new `pending_verification` state) and let the next poll tick retry, up to a small attempt cap, before
  falling back to today's pass-through behavior. This directly closes the "single transient failure =
  permanent wrong verdict" gap.
- **P0 — close the race between the two reconciliation cadences.** Either (a) have the per-CLI
  `_reconcile_jobs_unlocked()` path also attempt `_reconcile_terminal_jobs_json`-style GH verification
  before writing a failure-looking terminal status to `jobs.json` for any `requires_gh_write` job, or
  (b) make `_reconcile_jobs_unlocked` write a provisional (non-terminal-looking) status for
  `requires_gh_write` jobs and defer the user-visible terminal verdict until the daemon's verified pass
  has actually run at least once.
- **P1 — make the split explicit in the CLI output.** Until P0 lands, `synlynk jobs --all` should
  visibly flag any `requires_gh_write` job whose `gh_write_verified` is still `null`/`unknown` as
  "unverified" rather than surfacing synlynk's own best-guess failure status as if it were final.
- **P1 — dedupe/alert on repair no-ops.** `_reconcile_terminal_jobs_json`'s silent no-op when a
  `daemon_jobs` row is no longer `running` is itself a signal worth surfacing (it means a job will
  never get corrected) — log it, and surface a count in `synlynk status`.
- **P2 — fold into the Empirical Capability Assessment Policy.** Per `CLAUDE.md`, harness/model
  routing decisions are supposed to be driven by measured `pr_review_cycles`/`cost_entries` data. As
  long as the status labels feeding that measurement are this unreliable, any capability comparison
  built on them is suspect — this RCA's fix is a prerequisite for that policy's data quality, not just
  a UX nuisance.

## Verification

- Once P0 lands: re-run the same class of job (a `--requires-gh-write` review dispatch) and confirm
  `synlynk jobs --all`'s status converges to the `gh pr view`-confirmed ground truth without manual
  intervention, including in a deliberately-induced transient-failure test (e.g., temporarily revoking
  network access during the verification window) to confirm the retry path recovers instead of
  freezing a bad verdict.
- Spot-check the existing backlog of already-mislabeled jobs from this session (e.g. job-7d6a73dc,
  job-1c91a47c, job-49a7ea2f, job-bde25c37, referenced in gh:#2130's comments) — confirm whether a
  manual `cmd_jobs_reconcile_truth` pass now produces the same verdict the fix would have produced
  automatically, as a regression check.
