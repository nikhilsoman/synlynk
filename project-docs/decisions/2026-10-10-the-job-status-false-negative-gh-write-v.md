<!-- generated - source of truth is state.db -->
---
decision_id: dec-39b77de7
topic: "The job-status false-negative / GH-write-verification bug cluster (gh:#2130, #2136 [closed, PR #2160], #2137, #2138, #2139, #2158, #2163, #2121, and the closed-but-recurring #1377) has been deep-reviewed (findings posted to https://github.com/nikhilsoman/synlynk/issues/2137#issuecomment-6099351715). It breaks into 4 architecturally distinct root causes, not one bug:

CLUSTER A - jobs.json <-> daemon_jobs split-brain (LIVE-22 RCA, docs/rca/2026-10-08-LIVE-22-job-status-split-brain.md). Two job-status stores reconciled by two different code paths at two cadences, bridged by a one-way, non-retrying, single-attempt sync. PR #2160 only added a retry cap to _guard_unpushed_branch's internal branch-push check (jobs.py:4047); the general verification call path (_verify_daemon_terminal_status -> _apply_gh_write_verification, jobs.py:3968-4035) is still a bare, unretried call today. #2137/#2138/#2139 remain open against this gap. #2163 adds fresh 2026-10-10 field evidence this race is still live post-#2160, plus a possibly-separate 5th thread (an "instruction receipt untrusted, expected='0.23.0-dev'" version-staleness warning).

CLUSTER B - receipt-protocol gap on no-file-diff tasks. #1377 (closed 2026-09-05, "5/5 fixes shipped") does not hold for review-type/GH-write-only jobs whose entire work product is a GitHub API call with zero local file diff (#2130: 6/6 recurrence in one session). This is a classification-heuristic gap in _task_delivery_has_corroborating_activity, distinct from Cluster A's race. No dedicated ticket exists yet for this specific gap.

CLUSTER C - cost/token circuit breaker tripping on genuinely correct work (#2121, and now also directly observed this session on job-0d1aba31/gh:#2182: $5.83 actual vs ~$0.16 estimate, ~36x overrun, SCOPE_REVIEW_REQUIRED on complete, correct, tested work). Pure cost-estimate-vs-actual blowup, unrelated to GH-write verification plumbing - shares only the symptom (correct work, bad status label) with A/B.

CLUSTER D - oracle/job_truth contract-matching gap (#2158, new finding this review). synlynk/job_truth.py + synlynk/job_status_projection.py implement an already-built, parallel "canonical job truth" system (TriState enum, non-terminal unknown/verifying statuses, SYNLYNK_JOB_TRUTH_MODE rollout gate off/shadow/authoritative defaulting to shadow, its own DEFAULT_MAX_VERIFICATION_RETRIES=3 / DEFAULT_MAX_UNKNOWN_AGE_SECONDS=300) - architecturally designed to solve exactly the Cluster A problem (one-shot verification, no retry, terminal-status permanence) as a replacement architecture, not a patch. Currently wired into jobs.py at 4 call sites, all shadow/logging-only (record_shadow_comparison/project_job_status) - no call site ever consults rollout_mode() to actually gate the displayed status. #2158's oracle_decision_missing/unknown_contract symptom originates here, not from Cluster A's race.

Control case: unknown_contract/exit 1 is an overloaded generic code - confirmed this session (job-5d433064, an invalid --effort CLI flag, zero real commits) that it also fires for ordinary CLI-invocation errors unrelated to any of the 4 clusters. Don't assume every instance is a false negative.

DECISION NEEDED: fix sequencing and architecture strategy. The two live strategic options for Cluster A/D specifically (B and C are already correctly scoped as independent, no architecture decision needed there):

APPROACH 1 - Keep patching the legacy jobs.py path: continue #2137/#2138/#2139 as currently scoped (wrap _verify_daemon_terminal_status's call to _apply_gh_write_verification in the same retry-cap pattern PR #2160 already used for _guard_unpushed_branch; add CLI surfacing of "unverified" status per #2138/#2139).

APPROACH 2 - Finish and promote the job_truth/job_status_projection shadow oracle to authoritative: instead of patching the legacy race in multiple places, invest in flipping SYNLYNK_JOB_TRUTH_MODE from shadow to authoritative, having cmd_jobs/cmd_dispatch actually gate on rollout_mode()'s decision instead of the legacy jobs.json/daemon_jobs path. This was apparently already designed to solve exactly this problem but was never finished/wired in for real use.

Building both in parallel risks a second split-brain (between the legacy patches and the new oracle). Also weigh: a short Brainstorm-First design note may be warranted before implementation either way, but the decide panel's job here is to recommend WHICH strategy to design around, and what evidence would most cheaply de-risk picking wrong (e.g., can the shadow oracle's existing logged disagreement data from the past weeks tell us whether it already agrees with ground truth often enough to trust promoting it, rather than guessing).

Please recommend: (1) Approach 1, Approach 2, or a hybrid/sequencing (e.g. "ship Approach 1 narrowly as a stopgap now, concurrently evaluate Approach 2's shadow-log agreement rate, then migrate"), and (2) what the first concrete next step should be.
"
date: 2026-10-10
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
The job-status false-negative / GH-write-verification bug cluster (gh:#2130, #2136 [closed, PR #2160], #2137, #2138, #2139, #2158, #2163, #2121, and the closed-but-recurring #1377) has been deep-reviewed (findings posted to https://github.com/nikhilsoman/synlynk/issues/2137#issuecomment-6099351715). It breaks into 4 architecturally distinct root causes, not one bug:

CLUSTER A - jobs.json <-> daemon_jobs split-brain (LIVE-22 RCA, docs/rca/2026-10-08-LIVE-22-job-status-split-brain.md). Two job-status stores reconciled by two different code paths at two cadences, bridged by a one-way, non-retrying, single-attempt sync. PR #2160 only added a retry cap to _guard_unpushed_branch's internal branch-push check (jobs.py:4047); the general verification call path (_verify_daemon_terminal_status -> _apply_gh_write_verification, jobs.py:3968-4035) is still a bare, unretried call today. #2137/#2138/#2139 remain open against this gap. #2163 adds fresh 2026-10-10 field evidence this race is still live post-#2160, plus a possibly-separate 5th thread (an "instruction receipt untrusted, expected='0.23.0-dev'" version-staleness warning).

CLUSTER B - receipt-protocol gap on no-file-diff tasks. #1377 (closed 2026-09-05, "5/5 fixes shipped") does not hold for review-type/GH-write-only jobs whose entire work product is a GitHub API call with zero local file diff (#2130: 6/6 recurrence in one session). This is a classification-heuristic gap in _task_delivery_has_corroborating_activity, distinct from Cluster A's race. No dedicated ticket exists yet for this specific gap.

CLUSTER C - cost/token circuit breaker tripping on genuinely correct work (#2121, and now also directly observed this session on job-0d1aba31/gh:#2182: $5.83 actual vs ~$0.16 estimate, ~36x overrun, SCOPE_REVIEW_REQUIRED on complete, correct, tested work). Pure cost-estimate-vs-actual blowup, unrelated to GH-write verification plumbing - shares only the symptom (correct work, bad status label) with A/B.

CLUSTER D - oracle/job_truth contract-matching gap (#2158, new finding this review). synlynk/job_truth.py + synlynk/job_status_projection.py implement an already-built, parallel "canonical job truth" system (TriState enum, non-terminal unknown/verifying statuses, SYNLYNK_JOB_TRUTH_MODE rollout gate off/shadow/authoritative defaulting to shadow, its own DEFAULT_MAX_VERIFICATION_RETRIES=3 / DEFAULT_MAX_UNKNOWN_AGE_SECONDS=300) - architecturally designed to solve exactly the Cluster A problem (one-shot verification, no retry, terminal-status permanence) as a replacement architecture, not a patch. Currently wired into jobs.py at 4 call sites, all shadow/logging-only (record_shadow_comparison/project_job_status) - no call site ever consults rollout_mode() to actually gate the displayed status. #2158's oracle_decision_missing/unknown_contract symptom originates here, not from Cluster A's race.

Control case: unknown_contract/exit 1 is an overloaded generic code - confirmed this session (job-5d433064, an invalid --effort CLI flag, zero real commits) that it also fires for ordinary CLI-invocation errors unrelated to any of the 4 clusters. Don't assume every instance is a false negative.

DECISION NEEDED: fix sequencing and architecture strategy. The two live strategic options for Cluster A/D specifically (B and C are already correctly scoped as independent, no architecture decision needed there):

APPROACH 1 - Keep patching the legacy jobs.py path: continue #2137/#2138/#2139 as currently scoped (wrap _verify_daemon_terminal_status's call to _apply_gh_write_verification in the same retry-cap pattern PR #2160 already used for _guard_unpushed_branch; add CLI surfacing of "unverified" status per #2138/#2139).

APPROACH 2 - Finish and promote the job_truth/job_status_projection shadow oracle to authoritative: instead of patching the legacy race in multiple places, invest in flipping SYNLYNK_JOB_TRUTH_MODE from shadow to authoritative, having cmd_jobs/cmd_dispatch actually gate on rollout_mode()'s decision instead of the legacy jobs.json/daemon_jobs path. This was apparently already designed to solve exactly this problem but was never finished/wired in for real use.

Building both in parallel risks a second split-brain (between the legacy patches and the new oracle). Also weigh: a short Brainstorm-First design note may be warranted before implementation either way, but the decide panel's job here is to recommend WHICH strategy to design around, and what evidence would most cheaply de-risk picking wrong (e.g., can the shadow oracle's existing logged disagreement data from the past weeks tell us whether it already agrees with ground truth often enough to trust promoting it, rather than guessing).

Please recommend: (1) Approach 1, Approach 2, or a hybrid/sequencing (e.g. "ship Approach 1 narrowly as a stopgap now, concurrently evaluate Approach 2's shadow-log agreement rate, then migrate"), and (2) what the first concrete next step should be.


## Panel Inputs

### claude
[model=default; version=2.1.292 (Claude Code)]

Clusters A and D aren't independent problems competing for resources — they're the same problem at two layers of the same stack. A is "the legacy path races and doesn't retry." D is "a replacement system that already solves exactly that race exists, but nothing consults it." Patching A (Approach 1) without finishing D guarantees the second split-brain you're worried about: you'll have hardened the legacy retry logic *and* a shadow oracle disagreeing with it silently, and six months from now someone reopens this exact decision with twice the surface area.

The cheap de-risking move is sitting right there: `job_status_projection.py` has been running in shadow mode logging `record_shadow_comparison` against real jobs for presumably weeks. That's a dataset, not a guess. Before writing any design doc, pull the shadow-vs-legacy agreement rate, broken out by failure mode (specifically: does the oracle correctly resolve the cases where legacy's one-shot verification raced and got it wrong?). That single query answers the real question — "is the oracle already right more often than legacy, specifically on the cases we care about" — for near-zero cost, since the instrumentation is already in production.

Recommendation: hybrid, sequenced.

1. **Now, narrow stopgap on Cluster A only**: wrap `_apply_gh_write_verification`'s call site in `_verify_daemon_terminal_status` (jobs.py:3968-4035) with the same bounded retry-cap pattern PR #2160 used — not new architecture, just closing the exposed race with the pattern already proven safe. This unblocks #2137/#2138/#2139 without growing scope.
2. **Concurrently, pull the shadow-agreement data** — this is a data-pull, not a dispatch-worthy task, do it directly.
3. **Decision gate**: if agreement rate is high (especially on the specific race-condition cases), scope a Brainstorm-First design note for flipping `SYNLYNK_JOB_TRUTH_MODE` to `authoritative` and retiring the legacy verification path entirely — don't let both live long-term. If agreement is low or data is too thin, that itself is the answer: the oracle isn't ready, stopgap stays, and D gets a dedicated investigation ticket instead of a promotion plan.

Don't build both in parallel past step 1. The stopgap is small and bounded; everything past it should be gated on the shadow-log evidence, not built speculatively alongside it.

### agy
[model=default; version=1.3.3]

Last completed task: `feat(cli): add 'synlynk goal update' subcommand (gh:#2182)`
Next task from `todo.md`: `BS-7: brainstorm — skill pack interoperability + benchmarks (Superpowers/GStack/GSD)`

---

### Decision Panel Analysis: GH-Write Verification & Job Status Architecture

The 4-cluster root cause analysis clearly demonstrates why prior point fixes (such as PR #2160) failed to eliminate false negatives. Continuing to patch isolated call sites in `jobs.py` treats symptoms while preserving the underlying split-brain state engine.

#### Analysis of Options
* **Approach 1 (Legacy Patching)**: Wrapping `_verify_daemon_terminal_status` in retry bounds mitigates immediate race windows for Cluster A (#2137/#2138/#2139), but leaves `jobs.json` and `daemon_jobs` as competing stores and leaves Cluster D unaddressed.
* **Approach 2 (Oracle Promotion)**: Gating `cmd_jobs` and `cmd_dispatch` on `job_truth.py` / `job_status_projection.py` via `SYNLYNK_JOB_TRUTH_MODE` fundamentally addresses Clusters A and D by replacing single-attempt sync with stateful `TriState` evaluation and structured retries.

#### Recommended Sequencing Strategy
I recommend a **phased hybrid approach (Stopgap Approach 1 → Authoritative Approach 2 Migration)**:

1. **Immediate Stopgap (Approach 1)**: Wrap `_verify_daemon_terminal_status`'s call to `_apply_gh_write_verification` in [synlynk/jobs.py](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/docs+claude+tpm-daemon-autonomy-fix-design/worktrees/job-0d1aba31/synlynk/jobs.py#L3968-L4035) with the existing retry-cap helper to stop active field failures (#2137/#2138/#2139).
2. **Shadow Data De-risking**: Analyze logged `record_shadow_comparison` metrics from existing shadow runs to verify `job_truth` projection accuracy against ground truth.
3. **Oracle Promotion (Approach 2)**: Wire `rollout_mode()` checks into `cmd_jobs` and `cmd_dispatch`, promoting `job_truth` to authoritative state authority.
4. **Independent Cluster Fixes**: Update `_task_delivery_has_corroborating_activity` for zero-diff GH-write tasks (Cluster B) and adjust cost circuit breaker bounds for long-context runs (Cluster C).

#### First Concrete Next Step
The first concrete next step is to author a brief Brainstorm-First design spec at `docs/superpowers/specs/2026-10-11-job-truth-promotion-design.md` detailing the shadow log analysis query and the `rollout_mode()` activation criteria.

#### Position Statement
My position is to execute a phased hybrid strategy: ship the narrow `_verify_daemon_terminal_status` retry cap as an immediate stopgap fix, while concurrently evaluating shadow-log agreement metrics to safely promote the `job_truth` oracle to authoritative mode.

### codex
[model=default; version=codex-cli 0.162.1]

**Recommendation: use a staged hybrid, with Approach 1 as a narrowly scoped stopgap and Approach 2 as the strategic destination.**

The live evidence argues against waiting for the oracle migration: the general verification path still makes a bare, unretried call, and #2163 reports the race recurring after #2160. A capped retry plus clear CLI surfacing of “unverified” status would close that immediate gap. Keep this change confined to Cluster A; do not fold in the no-diff receipt heuristic (B) or cost circuit breaker (C), which have different causes and need separate fixes.

I would not promote the shadow oracle on the information provided. Its design appears aimed at the right architectural failure, but its call sites only log comparisons; that does not establish that its decisions match ground truth or that authoritative mode behaves safely across the relevant job types. Promoting it alongside legacy-path fixes could also leave two competing status authorities. First measure its logged disagreements against independently verified outcomes, especially GH-write-only jobs, terminal verification races, and unknown-contract cases. Treat ordinary CLI invocation errors as a separate control group so their overloaded `unknown_contract` code does not skew the result.

**The first concrete next step should be a short Brainstorm-First design note for the staged plan.** Specify the narrow retry/unverified stopgap, the shadow-log analysis and acceptance criteria for promotion, and how to avoid overlapping status authorities during migration. In parallel, inspect the existing shadow comparison logs to estimate agreement before committing to the oracle as the destination. Keep B and C independently tracked; the version-staleness warning also needs triage before being attributed to these clusters.

My position is: **design around Approach 2 as the intended end state, but ship Approach 1 narrowly first, and promote the oracle only after shadow evidence meets explicit criteria.**

### grok
[model=default; version=grok 1.0.50 (c58f321264ba)]

I'll ground the sequencing call in the review comment and the actual `job_truth` / verification call sites before recommending a strategy.Recommend a sequenced hybrid: keep the job-truth oracle as the only architecture for Clusters A and D, and ship one display-only stopgap so operators stop acting on a false terminal failure while that oracle is still unfit to promote.

Approach 2 is the strategy already chosen on 2026-10-03. `job_status_projection.promotion_gate` fails closed below 100 samples, on any unexplained disagreement, and on `contract_missing > 0`. `decide_job_outcome` still returns `unknown_contract` / `manual_review` before it inspects evidence whenever `requires_gh_write` is set and `task_type` is outside the five-keyword allowlist. #2158 is that bug. Flipping `SYNLYNK_JOB_TRUTH_MODE` to `authoritative` now would replace the legacy false failure with an oracle that cannot accept confirmed GitHub evidence. `rollout_mode()` is also unread by `cmd_jobs`; the four call sites only log.

Approach 1's retry cap does not close the race #2160 left open. #2163 shows merged PRs still labeled wrong after that patch. `_reconcile_jobs_unlocked` still writes a terminal status from local evidence on every CLI call, ahead of the daemon's one-shot `_verify_daemon_terminal_status` → `_apply_gh_write_verification`. Another retry inside the daemon poll does not stop that earlier write, and a second terminal writer beside the oracle is the split-brain to avoid.

The stopgap is #2137 option (b) plus #2138: for `requires_gh_write` jobs whose GitHub effect has not been consulted, keep the user-visible status provisional (`pending_verification` / unverified) instead of a best-guess failure. That matches the oracle's non-terminal `verifying` state and adds no new status writer. #2139 is a log line on that no-op. Leave Cluster B as its own no-diff receipt ticket, Cluster C on #2121, and #2163's `0.23.0-dev` receipt warning as a fifth thread. `unknown_contract` stays an overloaded code: job-5d433064 was a real CLI failure.

Shadow-versus-legacy agreement is the wrong test, because the legacy status is the bug. `job_status_shadow` can show how often the oracle is silent (`oracle_decision_missing`, `unknown_contract`) versus contradictory (`false_failure`). Ground truth is an independent `gh` replay of #2130, #2158, #2163, and job-5d433064, which the 2026-10-03 decision already set as the promotion bar.

**Position:** design around Approach 2. Do not promote it, and do not add another legacy retry writer. First step: run `promotion_gate` on the existing shadow rows, then replay those four jobs against `gh`. Only a gate that passes on that replay justifies an authoritative cutover. Until then, the provisional unverified label is the only Cluster A change that should land.

## Synthesis
Decision: Hybrid, sequenced — treat Approach 2 (job_truth oracle) as the destination architecture but do not promote it yet, and ship a narrow, non-terminal stopgap now rather than Approach 1's retry-cap patch.

All four panelists converge on the same structural point once pressed: Cluster D isn't a parallel problem to Cluster A, it's the already-built fix for Cluster A that nobody wired in. Patching `_verify_daemon_terminal_status`'s call to `_apply_gh_write_verification` with another retry cap (plain Approach 1) adds a second terminal-status writer next to an oracle that's also writing shadow decisions — that's the second split-brain the prompt warned about, and Grok's point lands: `_reconcile_jobs_unlocked` already writes a terminal status ahead of the daemon's one-shot verification, so a retry nested deeper in that path doesn't actually close the race, it just makes the existing writer retry before losing.

But Codex and Grok are also right that the oracle isn't provable yet: `job_status_projection.promotion_gate` fails closed below 100 samples or on any unexplained disagreement, the four `jobs.py` call sites only log via `record_shadow_comparison`/`project_job_status` and never consult `rollout_mode()`, and #2158 shows `decide_job_outcome` returning `unknown_contract`/`manual_review` before it even inspects evidence for GH-write jobs outside a narrow task-type allowlist — flipping to authoritative today would trade a false-failure bug for a confirmed-evidence-gets-ignored bug. So promotion is gated on data that doesn't yet exist in a trustworthy form.

The stopgap that actually fits both constraints — stop the field failures without adding a second terminal writer — is Grok's: for `requires_gh_write` jobs where the GitHub effect hasn't been consulted yet, surface a provisional/non-terminal status (`pending_verification`/unverified, matching the oracle's existing `verifying` TriState) instead of writing a best-guess failure. This is display/status-surfacing, not a new write-path, so it doesn't compete with the oracle architecture — it's consistent with where #2137/#2138/#2139 were already headed on the "surface unverified" half, just without adding Approach 1's extra retry-cap writer on the verification call site itself.

First concrete next step: before writing any design doc, run `promotion_gate` against the existing shadow-comparison rows and independently replay ground truth via `gh` for the known disputed cases (#2130, #2158, #2163, and the job-5d433064 control case) to see where the oracle is silent (`oracle_decision_missing`/`unknown_contract`) versus actively wrong (`false_failure`) versus correct. That number — not a guess — determines whether the next PR is "wire `rollout_mode()` into `cmd_jobs`/`cmd_dispatch`" or "fix `decide_job_outcome`'s allowlist gap first." In parallel, land the narrow provisional-status surfacing fix (no new terminal writer) to stop the active field pain immediately. Keep Cluster B (`_task_delivery_has_corroborating_activity` no-diff heuristic) and Cluster C (cost circuit breaker) on their own tickets — they share only the symptom, not the cause, and shouldn't block or be blocked by this sequencing decision.

## Decision
Decision: Hybrid, sequenced — treat Approach 2 (job_truth oracle) as the destination architecture but do not promote it yet, and ship a narrow, non-terminal stopgap now rather than Approach 1's retry-cap patch.

> Signatures: see 2026-10-10-the-job-status-false-negative-gh-write-v.json
