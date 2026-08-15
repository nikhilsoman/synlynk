---
decision_id: dec-r4-701consolidation
topic: "ROUND 4/4 — What changes for #331/#579/#426/#659 specifically, per issue, given Rounds 1-3?"
date: 2026-08-15
panel: [claude-direct-evidence]
status: approved
---

## Topic
Translate Rounds 1-3's findings into a per-issue disposition, since #701 asked
explicitly what changes for each named issue.

## Dispositions

**#331 (daemon_jobs status reconciliation never got GTV) — CLOSE.**
Evidence (Round 1): `_reconcile_daemon_jobs` demonstrably calls
`_inspect_worktree_git_state`/`_worktree_files_touched` in the current tree; PR
#867's own comment on the issue says "brings GTV to `_reconcile_daemon_jobs`." No
code gap remains. Action: close with a comment linking PR #867 and this spec; add
a regression test (if none exists) asserting `_reconcile_daemon_jobs` and the
legacy `_reconcile_jobs` produce parity on a shared mocked fixture (#701's
originally proposed guard (B), still not implemented — confirm during planning).

**#579 (job summary shows UNKNOWN/0-files for succeeded jobs) — CLOSE.**
Same fix, same evidence (PR #867 comment: "daemon reconcile no longer forces
empty files_touched / bare unknown for dead PIDs with worktree activity"). Close
alongside #331.

**#426 (Agy/Codex cannot perform GitHub write actions headless) — REFRAME, do not
close as-is.**
Evidence (Round 2): independently verified (job-381edf13, a second agent
re-checking via `gh pr view --json reviews` rather than trusting Agy's self-report)
that Agy *can* complete headless `gh pr review`/`gh pr comment` writes once
`~/.gemini/antigravity-cli/settings.json` carries the right scoped
`command(gh pr review)` etc. allow-rules. The issue's premise ("cannot perform")
is now stale. This repo's own CLAUDE.md harness-instructions table already
half-reflects this ("Agy headless can complete... when the machine-local settings
already contains scoped allow-rules; that precondition is operator-confirmed, not
reliably verifiable mid-task") — i.e., the gap is now "synlynk cannot verify this
precondition automatically," not "Agy cannot do the write." Action: retitle/refocus
#426 onto that narrower, still-real gap — add a preflight check (extend TC-6 or a
new TC-7) that inspects `~/.gemini/antigravity-cli/settings.json` for the required
`command(...)` entries before routing a gh-write task to Agy, and fails the routing
decision loudly (route to Codex/Grok or block) instead of silently dispatching and
discovering the gap mid-job. Codex remains excluded from this path per the sandbox
network constraint (separate, real, and unrelated to Agy's config gap).

**#659 (GitHub MCP review submissions silently cancelled 4/4) — KEEP OPEN,
attach concrete next step from Round 3.**
No fix attempted yet; root cause still "not yet confirmed" per the issue's own
text. Action: (a) implement Round 3's delivery-of-effect check
(`gh_write_verified`) so any future MCP-connector cancellation is caught
automatically instead of requiring a manual log grep — this closes the
*detection* gap immediately regardless of root cause; (b) as a parallel mitigation
independent of root-causing the MCP credential issue, route Codex's PR-review
GitHub-write step through the plain `gh pr review`/`gh pr comment` CLI (the path
#426's evidence shows works reliably for Agy) instead of the `github.add_review_to_pr`
/`add_comment_to_issue` MCP Apps tools, since the MCP path has a confirmed 100%
(4/4) failure rate and the CLI path has a confirmed working track record for the
same class of write. This sidesteps needing to root-cause the MCP connector's
credential scoping before shipping a mitigation.

**#935 (reviewer-dispatch reliability gap / stall-kill) — implement Round 3's
mechanism, then close.**
PR #939 is a valid interim mitigation, not the durable fix. Action: implement
Round 3's `--requires-gh-write`-gated delivery-of-effect check inside
`_check_job_stall`'s escape hatch, keep #939's `task_type == "review"` timeout as
a secondary/fallback signal, add the CI parity/coverage guard, then close #935 and
#701 together once both are verified against a *new* dispatched reviewer job (not
just code inspection) — matching this repo's own standing feedback memory:
"verify PR fixes via direct test run not CI/description."

**#701 itself — becomes the parent tracking issue for this spec's action items**,
closed only when all five dispositions above are shipped and independently
verified (not self-reported by the implementing job).

## Decision
Adopt all five dispositions above as the spec's action-item list. None require
further investigation before being scoped into an implementation plan — each is
grounded in code already read or an issue comment already on record.
