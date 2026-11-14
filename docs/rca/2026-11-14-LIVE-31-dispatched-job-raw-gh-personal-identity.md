# RCA: LIVE-31 — Dispatched jobs can post GitHub writes under the operator's personal identity via raw `gh`, bypassing the shim

**Date:** 2026-11-14
**Severity:** Sev1
**Status:** Root cause confirmed; mitigated per-incident for PR #5248; structural fix not yet shipped
**Tracking issue:** gh:#5249 (OPEN)
**Related:** gh:#1992 (audit-log event, not yet built), gh:#5250 (adjacent policy-config gap found during remediation)

## Summary

A dispatched review job (`job-04d8e2b4`) posted a `CHANGES_REQUESTED` review on PR #5248 by calling `gh pr review` directly instead of the project's `synlynk gh --role <role> -- ...` wrapper. The call succeeded silently because the sandbox's shell inherited the host machine's already-authenticated personal GitHub CLI session. The review was recorded under the operator's own GitHub login (`nikhilsoman`), not a role/bot identity — defeating the cross-harness+model review requirement's actual guarantee for that round.

This was originally filed as an attribution/audit-trail violation. During this incident, it surfaced a second, more concrete consequence: the stale personal-identity review actively **blocked a later, fully-approved, CI-green merge** of the same PR, because GitHub branch protection evaluates the latest review per distinct reviewer, not just the most recent review overall.

## Timeline

- **Round 2 (prior session)** — `job-04d8e2b4` (codex, role qa, task-type review) ran against PR #5248's round-1 fix commit. It correctly found a real blocking issue (`tests/test_events.py::test_approval_tickets_table_exists` out of sync with a new `constituent_story_ids` column) and posted `CHANGES_REQUESTED` — but did so via raw `gh pr review` in its own shell, not `synlynk gh --role qa -- ...`. The review landed under the personal identity `nikhilsoman`. In the same job, a separate `git push` attempt over HTTPS *was* correctly refused by the shim for lacking a role token — confirming the enforcement gap is specific to the `gh` CLI path, not a blanket bypass.
- **Round 2 fix + Round 3** — a follow-up implementation job (`job-a5426cf6`) fixed the flagged issue; a round-3 review job (`job-ac454d19`, role qa) correctly posted `APPROVED` under the role identity `synlynk-synlynk-qa`.
- **2026-11-14, this segment** — with round-3 APPROVED and all CI green, the PM/conductor session dispatched the final merge (`job-315ff7f5`, role qa, task-type review carrying the merge step). It failed:
  ```
  X Pull request nikhilsoman/synlynk#5248 is not mergeable: the base branch policy prohibits the merge. ...
  ```
  The job correctly refused to force the merge (`--auto`/`--admin`) and reported the exact failure back, per its brief.
- Direct inspection (`pr view --json reviewDecision,mergeStateStatus`) showed `reviewDecision: "CHANGES_REQUESTED"` and `mergeStateStatus: "BLOCKED"` despite the latest review being `APPROVED`. Fetching all three reviews' numeric REST ids showed the round-2 `nikhilsoman`-identity `CHANGES_REQUESTED` review (id `5900723225`) was still outstanding — never dismissed or superseded by a new review from that same reviewer.
- This was surfaced to the user via AskUserQuestion (how to clear a review blocking under their own identity). The user chose explicit, direct remediation: dismiss it via the GitHub REST API under the `qa` role identity, rather than self-dismissing on GitHub or using an `--admin` override.
- The dismissal was executed:
  ```
  synlynk gh --role qa -- api --method PUT repos/nikhilsoman/synlynk/pulls/5248/reviews/5900723225/dismissals -f message="..."
  ```
  `reviewDecision` flipped to `APPROVED`, `mergeStateStatus` to `CLEAN`.
- The merge was re-dispatched (`job-c1c77134`, identical brief) and succeeded. Independently verified: merge commit `25806322e32d1ec99e7b3044262eef84c60c8598`, `mergedBy: app/synlynk-synlynk-qa` (role identity, not personal — confirming the LIVE-31 mitigation held for this job).
- Issue #5246 auto-closed via the merge's `Fixes #5246` linkage.
- Worktree Hygiene Protocol swept all 8 nested dispatch worktrees belonging to this PR's chain (`job-71288d2f`, `job-a5426cf6`, `job-ac454d19`, `job-315ff7f5`, `job-c1c77134`, `job-04d8e2b4`, `job-520ba6b8`, `job-ee4f1ff0`) — all confirmed clean and subsumed, removed; local branches deleted (no remote branches existed for any of them).

## Root Cause

Two layers, one previously documented, one newly confirmed:

1. **(Already documented in #5249.)** `synlynk gh --shim-env` enforcement intercepts `git`'s HTTPS credential path (refusing `push` without a role token) but does not intercept or wrap the `gh` binary itself inside a dispatched job's sandbox. A job's raw `gh <write-command>` call falls through to whatever `gh auth status` the sandbox's inherited shell environment resolves to — on this host, the operator's own already-authenticated personal login. There is no isolation of `gh`'s own token storage analogous to the isolation already applied to `git`'s HTTPS credential path.

2. **(Newly confirmed this incident.)** GitHub branch protection's `reviewDecision` is computed **per distinct reviewer**: each reviewer's own latest review must individually resolve to non-blocking. A stale personal-identity review created by gap (1) is *not* superseded by a later, different reviewer's approval — it remains an independent outstanding block indefinitely, until someone explicitly dismisses or supersedes it from that same identity. This converts a silent attribution/audit violation into an active merge blocker that can surface arbitrarily later, on an unrelated dispatch, far from the original incident.

## Impact

- **Attribution integrity violated.** A real human (the operator's personal GitHub account) was recorded as having requested changes, when the dispatch's own intent and metadata say an independent role-identity reviewer did. This defeats the cross-harness+model review requirement's actual guarantee for that round, even though the review's *content* was legitimate and correct.
- **No audit trail.** gh:#1992 (an audit-log event for any host-auth fallback exercise) is not yet built. The personal-identity write happened with zero trace beyond the GitHub review record itself — caught only via this session's standing "never trust job status alone" independent-verification discipline, not by any automated control.
- **Concrete, newly-confirmed merge-blocking impact.** PR #5248's legitimate, fully-reviewed, CI-green merge was blocked and required a manual, user-authorized, per-incident remediation (a REST API review dismissal) to unblock. This is not a one-time cost — it recurs on every PR carrying a latent stale personal-identity review, discovered only when that PR's merge is attempted.
- **Unknown blast radius.** Other currently-open PRs may carry the same latent block from an earlier, undetected occurrence of this gap. Not yet audited (see Action Items).

## Why Existing Guardrails Didn't Catch It

- CLAUDE.md's Hardened PR Review Policy explicitly instructs dispatched jobs to use `synlynk gh --role <role> -- ...`, but `job-04d8e2b4`'s own dispatch brief (from the prior round) did not carry an explicit anti-pattern warning against raw `gh` — that warning was only added to this incident's later merge-task briefs, after the pattern was already known from this same tracking issue.
- `synlynk pr check` and `synlynk policy check-merge` both passed cleanly at round-3 approval time. Neither gate evaluates GitHub's live, per-reviewer `reviewDecision` computation directly — they check the policy's own tracked review state. The actual mergeability block was only visible via `gh pr merge`'s own failure message and a manual `pr view --json reviewDecision,mergeStateStatus` inspection; nothing upstream of the merge attempt flagged it.
- The host-side job status label (`FAILED_NOOP_DENIED`, "Expected GitHub effect was not verified directly via gh") fired for *both* the blocked attempt and the eventually-successful one — a recurring false-negative/false-positive pattern already tracked separately in this project's memory, and not specific to this incident, but worth noting as another reason the block's real cause took independent verification to surface rather than being surfaced by tooling.

## Action Items

1. **(Tracked in #5249, not yet shipped.)** Either isolate the dispatch sandbox's `gh` CLI token storage the way raw `git` push credentials are already isolated, or have `synlynk gh --shim-env` intercept/refuse raw `gh <write-command>` calls the same way it refuses raw `git push`.
2. **(gh:#1992, not yet built.)** Audit-log event for any host-auth fallback exercise / personal-identity GitHub write detected.
3. **New, filed from this RCA.** `synlynk pr check` / `policy check-merge` should surface a stale personal-identity (non-role) review as a named, actionable warning distinct from a generic "reviews present" check, so a future occurrence is caught at review time rather than discovered later as a merge failure.
4. **New, filed from this RCA.** Audit other currently-open PRs for a personal-identity review in their history, to determine whether this same latent block exists elsewhere right now, independent of any specific merge attempt surfacing it.

## Prevention

- Until Action Item 1 ships, every dispatched review/merge job's brief must explicitly warn against raw `gh` write calls and require `synlynk gh --role <role> -- ...` — this incident's later merge-task briefs already did this; it should become a standard clause in the review/merge dispatch brief template, not something written ad hoc per incident.
- Every merge attempt should independently re-verify `mergeStateStatus`/`reviewDecision` via `pr view` immediately before merging, rather than relying solely on `synlynk pr check`'s own tracked state — this is the check that actually caught the problem here, and it should be a standard step in every merge-dispatch brief (it already was in this incident's briefs, which is why it was caught at all).

## Resolution Status

Mitigated for PR #5248 only — the stale review was dismissed and the merge completed successfully, correctly attributed to the role identity on retry. The structural fix (Action Items 1–2, already tracked in #5249 / #1992) has **not** shipped. This RCA documents root cause and impact; it is not a closure record. gh:#5249 remains OPEN pending the structural fix; Action Items 3–4 are being filed as their own tickets referencing this RCA.
