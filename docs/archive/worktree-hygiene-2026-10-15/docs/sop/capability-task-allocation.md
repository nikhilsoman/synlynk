# Capability-Based Task Allocation & Empirical Capability Assessment Policy

> Moved out of root `CLAUDE.md` (2026-10-13, context-window-optimization plan) — same content, loaded on demand instead of resident in every session's root instruction file.

## Harness Capability Reassessment Protocol

**SUPERSEDED 2026-10-04 by the Empirical Capability Assessment Policy below.** This section's heuristic cadence (manual telemetry scan every ~25 jobs/monthly, hand-edited baseline doc) is kept here for historical context only; `docs/harness-capability-baseline.md` is suspended as ground truth. Do not re-derive routing from it — use `synlynk capability report` (once shipped, gh:#1993) or the raw `capability_ratings`/`cost_entries` tables instead.

<details><summary>Original protocol (suspended, kept for history)</summary>

1. **Trigger:** at least every ~25 dispatched jobs, or monthly, whichever comes first — same cadence discipline as the Worktree Hygiene Protocol's periodic audit above. Also trigger ad hoc after any LIVE-issue investigation that surfaces a new harness capability finding (e.g. LIVE-8/#1166).
2. **Scan:** review recent job telemetry (`synlynk jobs --all`, job logs for failures/cancellations) for patterns per harness — not just pass/fail counts, but *how* a job failed (sandboxed, timed out, stalled mid-task, went off-script). A green job-status is not sufficient evidence on its own; independently verify the claimed side effect the same way LIVE-8's retest did (`gh pr view --json reviews`, `git diff origin/main`, etc.) before treating a job as a real success or failure signal.
3. **Compare:** check each finding in `docs/harness-capability-baseline.md` against current evidence. A finding only gets re-tested if something material changed since it was recorded (harness version bump, sandbox policy change, an upstream fix) — not on a blind retry schedule.
4. **Update in one PR:** if reassessment finds drift (a harness got more/less reliable at something), update both `.synlynk/policy.json`'s `task_allocation` routing and `docs/harness-capability-baseline.md`'s table together, with the evidence cited in both places. This keeps dispatch routing and the documented baseline from diverging the way policy.json and CLAUDE.md's own routing table did before #426's hardening.
5. **No drift found:** still worth a one-line note in the baseline doc's row (or a dated comment) confirming it was checked, so the next reassessment knows the finding isn't stale just because it's old.

</details>

## Empirical Capability Assessment Policy (2026-10-04)

**Replaces the heuristic baseline above.** Decided 2026-10-04 (supersedes the #79 role-split rationale insofar as it relied on which harness happened to be convenient at the time): harness/model routing is no longer decided by hand-written capability tables. It is decided by measured outcomes, already captured in `capability_ratings` (per agent/model/story: `pr_review_cycles`, `dispatch_rework`, `micro_rework`, `quality`) and `cost_entries` (per harness/role/model/job: token counts, `total_cost_usd`).

**Everything is reassessable, including the Default Agent Role lock.** Claude's PM/review/deploy-only restriction is itself provisional pending data — it was drafted when Claude was the de facto default home harness, including for rxcc/vdowrx's Pulumi-IaC deploy work. Agy and Codex are believed comparably capable for PM/review; Grok and Meta Muse have not yet had the opportunity to be measured on PM/review/deploy tasks at all. **Deploy capability specifically must be re-tested through the Infra agent role**, not assumed from the original Claude-did-Pulumi-well precedent.

**Rules:**
1. **Minimum sample size:** a harness×task-type comparison needs ≥5 completed+merged jobs before it's allowed to influence routing. Below that, treat it as unmeasured, not as evidence of poor fit.
2. **Metrics:** median `pr_review_cycles` to merge (quality proxy) and `total_cost_usd` per merged PR (token economics), per harness×task-type, pulled from `capability_ratings`/`cost_entries` — not estimated, not recalled from memory of past incidents.
3. **`.synlynk/policy.json`'s `task_allocation` is generated output**, not hand-edited. It's annotated with the date/query it was generated from. Until the generator ships (gh:#1993), the current `task_allocation` block is an *interim default* open to override by any harness that clears the sample-size bar — it is not an authoritative capability ranking.
4. **Blocking dependency:** aggregate measurement requires `state.db` consolidation (#1926, Track 3) — capability/cost data is currently scattered across 11,000+ per-job workspace shards (`[[stray-local-state-db]]`, gh:#1831) and isn't reliably queryable in aggregate until that lands.
5. **Cadence:** fold into a `synlynk capability report` pull every ~25 jobs or monthly (same cadence as the superseded protocol above), but reading the measured tables, not re-litigating heuristics.

## Capability-Based Task Allocation

> ⚠️ **SUSPENDED as authoritative, 2026-10-04 — advisory/interim-default only.** This table was hand-authored heuristically and is superseded by the Empirical Capability Assessment Policy above. It remains the *current interim default* only until a harness clears the ≥5-merged-job sample-size bar on a given task type with better median `pr_review_cycles`/`total_cost_usd` than the incumbent. Grok and Meta Muse are explicitly flagged as not-yet-calibrated across every task type below, not excluded. `deploy` is now modeled as a task type in `.synlynk/policy.json`'s `task_allocation` (interim default: claude, fallback agy/codex) but carries zero empirical samples — it still needs to be tested via the Infra agent role before any harness (including Claude) can claim it empirically.

**Note:** "Harness" below means the execution backend (Claude/Agy/Grok/Codex) that runs a 
task, not the Agent (role) doing the work
- See `docs/glossary-agent-vs-harness.md`

| Role | Harness | Tasks |
| :--- | :--- | :--- |
| pm / review / deploy / brainstorm | Claude | pm, review, deploy, brainstorm |
| implement / test / css / templates / content / subpages | Agy | implement, test, css, templates, content, subpages |
| implement / test / canvas / js / infra | Grok | implement, test, canvas, js, infra |
| implement / test / refactor / cli-plumbing | Codex | implement, test, refactor, cli-plumbing |
Do not start a task outside your role column without explicit approval from Claude.

**GitHub write routing (#426):** Route any task that requires GitHub write actions to **Codex by default, Claude/Agy as fallbacks** (PR #1271, verified live in job `job-836e13a4`)
- ~~Grok's dispatch sandbox denies `bash` execution entirely in this environment (confirmed via `git diff origin/main` showing a total silent no-op despite a generic "OK, exit 0" job status — do not trust job-status alone for Grok gh-write attempts)~~ **SUPERSEDED 2026-10-04:** LIVE-13's underlying bug was fixed 2026-09-22 (PRs #1734/#1735) and reconfirmed by live retest (gh:#2034). `capability_probe.py` now flips `CAP_GH_WRITE` to true, and `dispatch.py` includes Grok last in `_GH_WRITE_HARNESS_PRIORITY`, pending >=5 empirical gh-write samples per the Empirical Capability Assessment Policy.
- Codex receives network access only for explicit `--requires-gh-write` dispatches
- Pass `--requires-gh-write` on synlynk dispatch to enforce the routing hint automatically; it now also auto-implies the `run:shell` permission grant and fails closed with a `RuntimeError` if no role is resolvable via `--as-agent`, `--story`, or `--role` (#569)

This table is generated from `.synlynk/config.json` so it tracks the repo's own routing rather than synlynk's default fleet assumptions.
