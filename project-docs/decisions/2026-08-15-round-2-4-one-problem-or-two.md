---
decision_id: dec-r2-701consolidation
topic: "ROUND 2/4 — Is 'sandboxed gh-write unreliability' and 'status self-report untruthfulness' one problem or two that got conflated in #701?"
date: 2026-08-15
panel: [claude-direct-evidence]
status: approved
---

## Topic
#701 bundles six issues under one title implying a single root cause. Round 1 found
a third failure mode (stall-kill) neither original problem covers. Does the
consolidation itself help, or does it obscure three independently-fixable code paths?

## Evidence

Three distinct subsystems, confirmed by file/line, each independently testable and
independently already fixed or broken:

| Problem | Code location | Checkpoint in job lifecycle | Status today |
|---|---|---|---|
| 1. Status truth (GTV) | `synlynk/jobs.py:2049` `_reconcile_daemon_jobs` | Post-exit: was the terminal status accurate? | Fixed (PR #867); tracking issues #331/#579 still open despite fix landing (hygiene gap, not code gap) |
| 2. GH-write identity/environment | `synlynk/dispatch.py:356` `_build_subprocess_env`, `synlynk/doctor.py` TC-6 | Pre-dispatch/runtime: can this job's environment actually authenticate a GitHub write under the correct identity? | Fixed for the CLI-env-stripping/fail-closed axis (#569 closed, PR #857); TC-6 preflight implemented; #426 (Agy/Codex headless capability) is stale-but-open — evidence (job-381edf13, cross-verified by an independent agent) shows Agy works correctly when `~/.gemini/antigravity-cli/settings.json` has the right scoped allow-rules, so this is now a documentation/config-discovery gap, not a code defect |
| 2b. GH-write delivery via MCP connector | Codex's `github.add_review_to_pr` / `add_comment_to_issue` MCP tool calls (no synlynk-side code — external connector) | Mid-execution: did the write actually land, independent of environment correctness? | Unresolved (#659 open, 4/4 failure rate, root cause "not yet confirmed," no fix attempted) |
| 3. Pre-exit liveness (stall-kill) | `synlynk/dispatch.py:517` `_check_job_stall` | Mid-execution: is a *still-running* job with no git-state signal actually dead, or just quiet? | Point-patched (PR #939), not durably fixed (Round 1) |

Each problem is independently reproducible and independently fixable without
touching the others' code. A fix to `_reconcile_daemon_jobs` cannot affect whether
`_check_job_stall` fires. A fix to the MCP connector's credential scope (2b) is
orthogonal to whether `_build_subprocess_env`'s CLI-level identity isolation (2) is
correct — 2 governs the `gh` CLI path Agy uses successfully; 2b governs a completely
different write path (Codex's GitHub MCP Apps connector) with no shared code.

## What actually links them
Not a shared root cause. A shared **architectural pattern** repeated across four
independent surfaces: whenever the system needs to answer "did the real-world
outcome happen," it currently defaults to trusting a local, cheap proxy signal
(process exit code, log file mtime, "job status: OK") instead of checking the
external ground truth (git state, GitHub API state) that the proxy is standing in
for. Problem 1 already generalized this correctly for the reconciliation
checkpoint. Problems 2b and 3 have not been generalized to it yet — 2b has no
verification step at all (job self-reports OK even when the write silently
cancelled), and 3's escape hatch only checks one kind of evidence (git state) at
one checkpoint (right before a kill decision).

Also linked practically: they get conflated in *observation* because they
co-occur in the same real workflow (dispatched PR-review jobs), so a single bad
session produces symptoms that look like "dispatch is broken" generally, even
though the underlying fixes are unrelated diffs in unrelated files.

## Decision
Keep them as **four separate, independently scoped fix surfaces** (status truth,
identity/environment, MCP delivery-verification, pre-exit liveness) rather than one
consolidated code change. But adopt **one shared verification principle** across
all four — "ground truth beats proxy signal, checked at every lifecycle
checkpoint, enforced not just documented" — as the spec's unifying design
constraint, and require any future job-lifecycle code path to satisfy it before
merge (see Round 3's proposed mechanism and CI guard). This directly answers the
brainstorm's framing question: they are two-going-on-four problems that share a
principle, not a cause — consolidating the *fix philosophy* is right; consolidating
the *code* would be wrong, since the surfaces don't share state or call paths.
