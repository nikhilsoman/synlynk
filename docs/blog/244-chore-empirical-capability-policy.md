---
title: "Suspending the Policy We Wrote for Our Own Convenience"
date: 2026-10-04
series: "Building the OS for Multi-Agent Development"
post: 244
pr: "1994"
issue: "1990,1991,1992,1993"
status: published
author: "synlynk team"
version: "0.25.0-dev"
tags: [posts, policy, capability-assessment, pr-review]
type: story
---

## The Broader Goal at the End of the Previous PR

PR5 (#1967) closed gh:#1924 — all five harnesses (Codex, Grok, Agy, Claude, local) now route
through dedicated `HarnessAdapter` implementations. The goalpost coming out of that PR was a
cost-anomaly thread to pull (#1969), not a policy question. This PR is a deliberate detour from
that thread, prompted directly by Nikhil rather than by anything the adapter work surfaced.

## Strategic Shift in This PR

Nikhil named the shift plainly: the Default Agent Role lock (Claude = PM/review/deploy only,
Agy/Grok/Codex = implement/test, decided 2026-06-28, gh:#79) was drafted at a moment when Claude
happened to be the best harness experience available and became his default home harness. That's
a fact about convenience at one point in time, not a measured capability finding — and synlynk
has been quietly building the infrastructure to measure capability for a while (`capability_ratings`,
`cost_entries`, `synlynk capability sweep`) without ever wiring it into routing. This PR is the
decision to stop treating the heuristic table as policy and start treating the measurement
infrastructure as policy, even though it means putting Claude's own privileged role back on the
table.

Nikhil was explicit that the reassessment includes the lock on *himself as PM* too: "Agy & Codex
are as good and Grok + Muse haven't had the opportunity yet." Deploy specifically traces back to a
narrower historical fact — Claude handled rxcc/vdowrx's Pulumi IaC well at the time — not a general
finding that Claude is the right deploy harness everywhere. That specific claim now needs
re-validation through each project's Infra agent role before it's trusted again.

Alongside the capability reassessment, Nikhil asked for three independent hardening measures to
the PR review process, to make the empirical data trustworthy once it starts accumulating:
exclusive GOVERNS adherence for every dispatched job, a hard line against any agent/harness ever
touching his personal GitHub token, and a requirement that reviewer and implementer differ in
harness *and* model, not just role.

## What This PR Shipped

Before writing anything, the host-auth escape hatch (`SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH`) was
verified against the personal-token requirement specifically, since that's a security claim and
not just a policy preference. Tracing `synlynk/dispatch.py`'s `_gh_write_allow_host_auth()` and
`_build_subprocess_env()` confirmed the variable is read only from the *dispatching* process's own
shell and is absent from `_ENV_ALLOWLIST_BASE` — a dispatched job cannot see or self-grant it. No
code gap, no exploit path; the only thing worth adding is audit logging so a manual override is
distinguishable from routine traffic (gh:#1992).

With that confirmed safe, the PR:

- Adds a `capability_policy` block to `.synlynk/policy.json`: empirical mode, a suspension date and
  rationale, a minimum sample size of 5 merged jobs before a harness×task-type comparison can
  influence routing, and the two metrics that matter — median `pr_review_cycles` (quality proxy)
  and `total_cost_usd` per merged PR (token economics) — both already captured in
  `capability_ratings`/`cost_entries` and already queried by `doctor.py`'s existing health check,
  just never fed back into routing.
- Marks `task_allocation` as an interim default rather than an authoritative ranking, flags Grok and
  Meta Muse as not-yet-calibrated (not excluded), and adds a `deploy` task type — not previously
  modeled at all — with Claude/Agy/Codex as calibration-eligible pending Infra-role re-validation.
- Adds `merge_authority.cross_harness_review_required` and a `governs_authority` block requiring a
  linked GOVERNS goal/story on every dispatched job, plus the `host_auth_fallback.audit_log_required`
  flag.
- Hand-edits `CLAUDE.md` (project and global) rather than running `synlynk instructions update` —
  `.synlynk/config.json` lacks the `roles` key the auto-repair generator expects, so a blind
  regen would have replaced the current detailed table with generic fallback text. The managed
  Harness Instructions block gets inline suspension annotations instead of a rewrite.
- Marks `docs/harness-capability-baseline.md`'s hand-written findings as corroborating evidence
  only, no longer authoritative for routing.
- Files four follow-up issues for enforcement code that doesn't exist yet: GOVERNS hard-fail
  gating (#1990), cross-harness+model review enforcement (#1991), host-auth audit logging (#1992),
  and the `synlynk capability report` generator itself (#1993) — which depends on `state.db`
  consolidation (#1926) before aggregate queries across the current 11,000+ scattered workspace
  shards (#1831) are reliable.

## Caught in Review

This PR's own doc-threaded issue numbers needed a correction pass — the first draft of the
cross-references (gh:#1991/#1992/#1993) was written before the issues existed and didn't match
the order they were actually filed in. Fixed by grepping every `gh:#199[0-3]` reference across
`CLAUDE.md` and `.synlynk/policy.json` and reconciling against the real issue numbers before
commit, rather than trusting the draft numbering.

## What Was Achieved Toward the Long-Arc Goal

The gap this closes isn't a capability gap in any one harness — it's that synlynk had been
quietly building the exact infrastructure (`capability_ratings`, `cost_entries`,
`capability sweep`) to answer "which harness is actually best at this task" empirically, while its
own routing policy and its own PM's role lock kept answering that question heuristically instead.
This PR doesn't change any routing yet — it suspends the heuristic's authority and commits to
measuring before the next change. It also doesn't resolve whether Claude keeps PM/review/deploy;
that's explicitly left open pending data.

## The New Goalpost

Nothing routes empirically yet — the generator (#1993) is unbuilt and blocked on state.db
consolidation (#1926), and the two review-hardening enforcement points (#1990, #1991) are policy
intent without a gate. The next goalpost is building that gate before dispatching the next batch
of parallel Track work (#1985-#1989), since that batch is also meant to be the first real dataset
this policy will be measured against.

Refs #1990, #1991, #1992, #1993, #1926, #1831, #79.
