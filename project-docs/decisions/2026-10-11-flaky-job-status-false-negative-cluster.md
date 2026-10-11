<!-- generated - source of truth is state.db -->
---
decision_id: dec-536d79aa
topic: "Flaky job-status false-negative cluster: #2137, #2138, #2139, #2130, #2163 (open), plus related #2158 and #2121 (cost-circuit-breaker tripping on correct output). Root cause already established in docs/rca/2026-10-08-LIVE-22-job-status-split-brain.md (sev1, root-caused, no code fix shipped): synlynk has two job-status stores reconciled by two different code paths at two different cadences. `.synlynk/jobs.json` is written by `_reconcile_jobs_unlocked()` (synlynk/jobs.py:2014) on every CLI invocation using only cheap local evidence (log text, git worktree state) — never a live GitHub call. `daemon_jobs` (SQL table in state.db) is what `synlynk jobs --all` actually reads (`cmd_jobs`, jobs.py:4607), reconciled only by the daemon's poll loop via `_reconcile_daemon_jobs()` (jobs.py:3997). The only bridge is `_reconcile_terminal_jobs_json()` (jobs.py:3471): it only acts on a daemon_jobs row still marked 'running' and NEVER overwrites an already-terminal row — so a job gets exactly one shot at live GitHub verification, and if that shot hits a transient failure (verified=None/"unknown" passes the pre-existing wrong local status through unchanged) or never runs because the row already left 'running' some other way, the wrong verdict is permanent with no self-healing retry. PR #2160 already merged and closed #2136/#2130's original trigger, but does NOT fix #2137/#2138/#2139/#2163 — those remain open on this same root cause.

This session alone collected 2 more live instances (job-ff128051 Codex, job-7e404db7 Grok, both on PR #2193) of jobs self-reporting failure-shaped terminal states (unpushed_branch/exit 1/insufficient_evidence) while the underlying GitHub PR had genuinely merged — see memory job-status-false-negative-rca-1377.md's 2026-10-11 addendum. This is now an 8+ instance pattern since 2026-09-04 across 5 previously-fixed root causes (#1379/#1380/#1381/#1382/#1383, all shipped same-day under #1377) plus this newer, structurally deeper split-brain class.

Decide: what is the right fix sequencing and architecture for closing this cluster for good — e.g. (a) make `_reconcile_terminal_jobs_json` retry-capable and able to re-open/upgrade an already-terminal row when stronger verified evidence later arrives (per the state-transition/revision-semantics direction already endorsed in the 2026-10-03 decide panel dec-5d37b005 on PR #1949), vs (b) collapse the two stores into one single source of truth and eliminate the bridge entirely, vs (c) some other approach. Also: how should #2158 and #2121 (cost-circuit-breaker tripping on correct output) be triaged — are they instances of this same split-brain class or a separate bug? Propose concrete fix scope/sequencing and ownership (which should be dispatched to Agy/Grok/Codex per this project's role split, Claude stays PM/review)."
date: 2026-10-11
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
Flaky job-status false-negative cluster: #2137, #2138, #2139, #2130, #2163 (open), plus related #2158 and #2121 (cost-circuit-breaker tripping on correct output). Root cause already established in docs/rca/2026-10-08-LIVE-22-job-status-split-brain.md (sev1, root-caused, no code fix shipped): synlynk has two job-status stores reconciled by two different code paths at two different cadences. `.synlynk/jobs.json` is written by `_reconcile_jobs_unlocked()` (synlynk/jobs.py:2014) on every CLI invocation using only cheap local evidence (log text, git worktree state) — never a live GitHub call. `daemon_jobs` (SQL table in state.db) is what `synlynk jobs --all` actually reads (`cmd_jobs`, jobs.py:4607), reconciled only by the daemon's poll loop via `_reconcile_daemon_jobs()` (jobs.py:3997). The only bridge is `_reconcile_terminal_jobs_json()` (jobs.py:3471): it only acts on a daemon_jobs row still marked 'running' and NEVER overwrites an already-terminal row — so a job gets exactly one shot at live GitHub verification, and if that shot hits a transient failure (verified=None/"unknown" passes the pre-existing wrong local status through unchanged) or never runs because the row already left 'running' some other way, the wrong verdict is permanent with no self-healing retry. PR #2160 already merged and closed #2136/#2130's original trigger, but does NOT fix #2137/#2138/#2139/#2163 — those remain open on this same root cause.

This session alone collected 2 more live instances (job-ff128051 Codex, job-7e404db7 Grok, both on PR #2193) of jobs self-reporting failure-shaped terminal states (unpushed_branch/exit 1/insufficient_evidence) while the underlying GitHub PR had genuinely merged — see memory job-status-false-negative-rca-1377.md's 2026-10-11 addendum. This is now an 8+ instance pattern since 2026-09-04 across 5 previously-fixed root causes (#1379/#1380/#1381/#1382/#1383, all shipped same-day under #1377) plus this newer, structurally deeper split-brain class.

Decide: what is the right fix sequencing and architecture for closing this cluster for good — e.g. (a) make `_reconcile_terminal_jobs_json` retry-capable and able to re-open/upgrade an already-terminal row when stronger verified evidence later arrives (per the state-transition/revision-semantics direction already endorsed in the 2026-10-03 decide panel dec-5d37b005 on PR #1949), vs (b) collapse the two stores into one single source of truth and eliminate the bridge entirely, vs (c) some other approach. Also: how should #2158 and #2121 (cost-circuit-breaker tripping on correct output) be triaged — are they instances of this same split-brain class or a separate bug? Propose concrete fix scope/sequencing and ownership (which should be dispatched to Agy/Grok/Codex per this project's role split, Claude stays PM/review).

## Panel Inputs

### claude
[model=default; version=2.1.292 (Claude Code)]

**Analysis**

This is a correctness/architecture decision, not an implementation task — staying in PM/review lane.

The RCA nails the bug: two stores, asymmetric reconciliation cadence, and a bridge that fires exactly once and never downgrades a terminal verdict. Option (a) — making `_reconcile_terminal_jobs_json` retry-capable/revision-aware — is strictly necessary regardless of what else happens, because even a unified store still needs a policy for "verdict changed after the fact" (GitHub state itself is eventually-consistent from synlynk's point of view). Option (b) — collapsing to one store — is the correct end state but is a bigger, riskier migration (state.db schema change, daemon + CLI both need to read/write the same path, migration of existing `.synlynk/jobs.json` artifacts across live worktrees). Shipping (b) first, blocking on (a), would leave the 5 open issues unfixed for longer with no proportional safety gain.

**Sequencing:** do (a) now as the hotfix — add a bounded retry/re-verification pass that can transition a terminal row from failure-shaped → merged (and vice versa) whenever a stronger-evidence signal (live `gh pr view`) arrives, gated by the revision-semantics direction already endorsed in dec-5d37b005. This directly closes #2137/#2138/#2139/#2163 and likely #2130 if not already covered by #2160. Follow with (b) as a separate, larger design-spec'd effort (new spec under `docs/superpowers/specs/`) to eliminate the bridge entirely — don't block the hotfix on it.

**#2158/#2121 triage:** cost-circuit-breaker tripping on correct output is very likely a *consumer* of the same false-negative signal (breaker almost certainly reads the same stale/terminal-mismatched status to decide "job failed, count against budget"), not an independent bug. Verify by checking what status source the breaker reads before assuming a shared fix — don't fold them in blind.

**Recommendation:** dispatch (a) to Codex (refactor/cli-plumbing lane, and it already owns GH-write-adjacent code per routing) as the immediate fix with explicit test coverage for the "upgrade after terminal" transition; write the (b) design spec next (brainstorm-first, PM-owned) before any dispatch; triage #2158/#2121 by reading the breaker's status source — fold into (a)'s PR only if confirmed same root cause, otherwise file separately.

### agy
[model=default; version=1.3.3]

### Status
Last completed task: Triaged LIVE-22 root-cause RCA on job-status split-brain.
Next task: Formulate decision panel recommendation on architecture, triage, and execution sequencing for #2137 cluster.

---

### Analysis & Triage

1. **Architecture & Sequencing: Hybrid Two-Phase Strategy (Option A → Option B)**
   - **Phase 1 (Immediate mitigation / Option A):** Immediate single-source-of-truth refactoring (collapsing stores) carries high regression risk across the 3,600+ test suite and daemon concurrency models. The right immediate move is adopting **revision semantics / monotonic lattice upgrades** in `_reconcile_terminal_jobs_json` (jobs.py:3471). A terminal status must not be write-once: verified remote evidence (`merged`, verified PR exit) strictly dominates local speculative heuristics (`unpushed_branch`, `exit 1`, `insufficient_evidence`). Adding a finite, backoff-based retry window for jobs where `verified is None` provides self-healing without unbounded polling.
   - **Phase 2 (Architectural convergence / Option B):** Deprecate `.synlynk/jobs.json` as a mutable authority. Treat `state.db` as the sole canonical source of truth, converting `jobs.json` into a read-only projection/cache generated directly from `daemon_jobs`.

2. **Triage of #2158 & #2121 (Cost-circuit-breaker false triggers)**
   - **Verdict: Functionally distinct bug class, triggered by split-brain downstream.** 
   - When a job gets stuck in an un-reconciled or pseudo-failed state, retry loops, duplicated dispatches, or miscalculated runtime deltas cause the cost evaluator to evaluate incomplete state or trip breakers despite valid downstream output. They must be tracked as a separate bug (P2), but sequenced immediately after Phase 1, as fixing the state machine eliminates the stale-run cascades feeding into the cost checker.

3. **Ownership Allocation (per synlynk matrix)**
   - **Codex (CLI Plumbing & Core Subsystems):** Implement Phase 1 lattice transition logic and monotonic upgrades in `synlynk/jobs.py` (`_reconcile_terminal_jobs_json`).
   - **Agy (Verification Tests & TDD Contracts):** Write TDD test fixtures for state machine transitions, simulating GitHub API transient timeouts followed by merged outcomes to verify self-healing across `#2137/#2138/#2139/#2163`.
   - **Grok (Infra & State DB):** Scope the Phase 2 schema consolidation in `state.db` and audit daemon poll intervals.
   - **Claude:** PM, spec approval, and PR review.

### Position
I recommend **sequencing Option A first as an immediate monotonic upgrade fix**, followed by **Option B to collapse the stores**. Specifically: make `_reconcile_terminal_jobs_json` state-upgradeable so verified truth overrides speculative failures, assign the implementation to **Codex**, and dispatch the test verification harness to **Agy**. Treat #2158 and #2121 as secondary telemetry bugs decoupled from the core reconciliation fix.

### codex
[model=default; version=codex-cli 0.162.1]

The durable fix is **one authoritative job state, with retryable verification and revision semantics**. Treating the bridge as the permanent architecture would leave two stores with different update cadences and competing verdicts; making that bridge retry-capable is a useful containment step, not closure.

Sequence the work in two stages:

1. **Contain the false negatives.** Change daemon reconciliation so a transient or unknown GitHub result does not become a permanent verdict. Persist verification status and retry eligible terminal rows with bounded backoff. Permit a later, stronger verified result to revise an earlier local terminal result, recording the prior state and evidence. Preserve safety against stale updates with explicit transition rules and revision checks. Add regression coverage for both PR #2193 instances and the one-shot failure paths.
2. **Remove the split-brain design.** Make the SQL job store authoritative for CLI reads and writes, and migrate local JSON reconciliation into that state model or retire the JSON store after compatibility needs are handled. Centralize transitions, evidence strength, and revision history. Keep GitHub verification in the daemon or a single shared service, but ensure every job can be re-evaluated without relying on a row remaining `running`.

Treat #2158 and #2121 as **separate until evidence links them**. A cost circuit breaker firing despite correct output points to cost accounting, thresholds, or output-validation ordering; it is not explained by the two job-status stores. Cross-check their job records and timestamps for shared reconciliation symptoms, then route any cost-specific failure to its own RCA and fix.

Ownership: Claude should coordinate PM and review. Assign retry behavior, revision semantics, and tests to **Codex** (CLI plumbing/core ownership); assign the larger store consolidation to **Grok** (infra ownership), subject to harness routing and a committed, signed-off spec and plan. **Agy** can take focused test or documentation tasks within its role. Do not dispatch implementation until the design spec is committed and signed off, per the harness sequence.

**Recommendation: contain the false negatives first, then converge on a single authoritative job store; do not treat bridge retries alone as the final fix. Triage the cost-circuit-breaker reports separately unless investigation establishes a direct causal link.**

### grok
[model=default; version=grok 1.0.50 (c58f321264ba)]

I'll read the RCA, the prior decide-panel direction, and the two reconciliation paths before recommending a fix sequence.The permanent wrong verdict is the absorbing terminal write. The two stores only decide when that write happens. `_reconcile_terminal_jobs_json` and `_persist_daemon_job_terminal(only_running=True)` give each job one GitHub check. `None` or `unknown` keeps the cheap local status, and a row that has already left `running` is never revisited. PR #2160's retry inside `_guard_unpushed_branch` only delays the first settle. `_promote_merged_pr_result` still omits `unpushed_branch`, so job-ff128051 and job-7e404db7 can stay failed after a real merge. Collapsing `.synlynk/jobs.json` and `daemon_jobs` first would keep that same rule in whichever table survives. dec-5d37b005 already requires non-absorbing transitions, a verification deadline, and remote-effect precedence before any oracle cutover. The shadow oracle is not that store yet: `decide_job_outcome` returns on `unknown_contract` before it considers a verified GitHub effect (#2158).

Ship three PRs, one writer module each.

1. Codex owns `synlynk/jobs.py`. Add an evidence-ranked correction next to the running-only settle. A later verified merge, review, or comment appends a revision and replaces a weaker terminal label: `unpushed_branch`, `task_delivery_failed`, `insufficient_evidence`, a bare exit 1, and `circuit_breaker_tripped` only when the process was not actually killed. `unknown` stays `pending_verification` up to a small attempt cap, then becomes `failed_verification`. The per-CLI reconciler publishes that provisional status for `requires_gh_write` jobs, so `synlynk jobs --all` does not show a failure during the daemon gap. Replay job-ff128051, job-7e404db7, and the #2137, #2138, #2139, and #2163 shapes, then backfill stuck rows with the existing reconcile-truth command.

2. Agy owns `synlynk/job_truth.py`, still in shadow mode. Move the `unknown_contract` return to after verified-remote precedence, and fixture the same jobs. That closes #2158 before promotion.

3. Claude reviews. Reader cutover, and retirement of `jobs.json` as a status writer, wait on the 2026-10-11 writer inventory and a numeric shadow gate. That is the store collapse, done after the revision rule exists.

#2121 stays on the #2133 cost track: stale graph and context assembly inflating a correct task. A breaker label that outlives a real effect is PR 1's allow-list. Retuning breaker ceilings will not close #2137.

Ship the ranked correction on `daemon_jobs` now, fix the oracle's `unknown_contract` trap in parallel, and collapse the two stores only at reader cutover. #2158 blocks that cutover. #2121 is outside this cluster.

## Synthesis
**Synthesis**

All four panelists converge on the same shape: treat retry/revision semantics in the existing bridge as the immediate containment fix, and treat full store collapse as a separate, larger follow-on — not a blocker. Nobody argues for (b) first; the risk/cost of a state.db-schema migration under live daemon traffic clearly outweighs the benefit of closing 5 open sev1-adjacent issues faster with the smaller fix. Codex is the converged owner for the core `jobs.py` change (CLI-plumbing/core-subsystem lane, matches existing routing), Claude stays PM/review, and the store-collapse work gets a design spec before any dispatch — consistent with the Design → Plan → Build sequence and dec-5d37b005's revision-semantics direction.

On #2158/#2121: Codex and Claude's "likely related but verify, don't fold blind" position is the right default caution, but Grok's read is more specific and more useful to act on — `decide_job_outcome` in `job_truth.py` returns on `unknown_contract` *before* it ever weighs verified-remote evidence, which is structurally the same absorbing-terminal-write bug, just in the shadow-oracle module rather than `_reconcile_terminal_jobs_json`. That's concrete enough to assign as its own small fix rather than leaving it as an open question.

**Decision:** Ship this as three scoped PRs, not one. (1) Codex fixes `_reconcile_terminal_jobs_json`/`_persist_daemon_job_terminal` in `synlynk/jobs.py` to make terminal verdicts revisable — rank evidence strength (verified GitHub merge/review > local heuristic > `unknown`), let a later stronger signal upgrade an already-terminal row instead of being absorbed, cap `unknown` in a bounded `pending_verification` retry window before it falls back to a labeled `failed_verification`, and extend the fix path currently missing `unpushed_branch` so job-ff128051/job-7e404db7-shaped cases resolve correctly; add regression tests replaying #2137/#2138/#2139/#2163 and the two PR #2193 instances. (2) Separately, fix the same class of bug in `job_truth.py`'s `decide_job_outcome` — move the `unknown_contract` early-return to after verified-remote-evidence is checked — and treat this as the actual fix for #2158 (triage verdict: same split-brain root-cause family, different module, not a cost-accounting bug); confirm #2121 independently by checking what status source its circuit breaker actually reads before assuming it's covered by either fix, and only fold it in if that check confirms shared root cause. Route both (1) and (2) to Codex as one coordinated dispatch (or two small sequential ones) since they're the same fix pattern in sibling modules. (3) The full single-source-of-truth store collapse is a separate PM-owned effort: write a design spec under `docs/superpowers/specs/` next, informed by the 2026-10-11 status-writer inventory already in flight, before dispatching any implementation — do not block (1)/(2) on it, and route it to Grok (infra/state-db ownership) once the spec is committed and signed off. Claude reviews all three as non-author per standard PR discipline.

## Decision
**Decision:** Ship this as three scoped PRs, not one. (1) Codex fixes `_reconcile_terminal_jobs_json`/`_persist_daemon_job_terminal` in `synlynk/jobs.py` to make terminal verdicts revisable — rank evidence strength (verified GitHub merge/review > local heuristic > `unknown`), let a later stronger signal upgrade an already-terminal row instead of being absorbed, cap `unknown` in a bounded `pending_verification` retry window before it falls back to a labeled `failed_verification`, and extend the fix path currently missing `unpushed_branch` so job-ff128051/job-7e404db7-shaped cases resolve correctly; add regression tests replaying #2137/#2138/#2139/#2163 and the two PR #2193 instances. (2) Separately, fix the same class of bug in `job_truth.py`'s `decide_job_outcome` — move the `unknown_contract` early-return to after verified-remote-evidence is checked — and treat this as the actual fix for #2158 (triage verdict: same split-brain root-cause family, different module, not a cost-accounting bug); confirm #2121 independently by checking what status source its circuit breaker actually reads before assuming it's covered by either fix, and only fold it in if that check confirms shared root cause. Route both (1) and (2) to Codex as one coordinated dispatch (or two small sequential ones) since they're the same fix pattern in sibling modules. (3) The full single-source-of-truth store collapse is a separate PM-owned effort: write a design spec under `docs/superpowers/specs/` next, informed by the 2026-10-11 status-writer inventory already in flight, before dispatching any implementation — do not block (1)/(2) on it, and route it to Grok (infra/state-db ownership) once the spec is committed and signed off. Claude reviews all three as non-author per standard PR discipline.

> Signatures: see 2026-10-11-flaky-job-status-false-negative-cluster.json
