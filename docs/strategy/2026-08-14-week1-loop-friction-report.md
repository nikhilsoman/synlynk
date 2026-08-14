# Week 1 Loop Friction Report — Attribution Failures & Prompt Friction

**Status:** Complete
**Feeds:** [road-to-autonomous-ops.md](road-to-autonomous-ops.md) — "2026-08-10 to 2026-08-16: Contract and dogfood" week, item "Measure attribution failures and prompt friction," input to the 2026-08-17 TPM/session MVP design.
**Scope:** Friction observed while manually running the autopilot-lite loop (goal → plan → stories → dispatch → verification → PR → review/merge → costs → devlog → roadmap reconciliation) across the GOVERNS event-contract extension, v0.13.1 release, and v0.14.0 epic closure work, 2026-08-06 through 2026-08-14.

## Why this doc exists

The road-to-autonomous-ops plan calls for closing the execution loop with a durable TPM layer, but that design should be grounded in where the *manual* version of the loop actually broke down — not assumed pain points. This is that ground-truth input. Each entry below is something that was directly observed and fixed or worked around during real dispatch/review/release cycles this week, not a hypothetical.

Findings are grouped into two categories per the task framing:
- **Attribution failures** — cases where the system's own status/tracking didn't reflect what actually happened, requiring manual verification to catch.
- **Prompt/process friction** — cases where the mechanics of dispatching, reviewing, or releasing cost extra manual steps or produced confusing output, independent of whether tracking was accurate.

## Attribution failures

These are the ones a TPM loop must not blindly trust — each one caused (or would have caused, if unverified) a false-positive "done" signal.

### 1. `synlynk jobs --summary` under-reports changed files (#202, recurred)
`synlynk jobs --summary job-e2c331a5` reported **"files: 0 touched"** for a dispatch job that had in fact made a 207-insertion/58-deletion change across 2 intended files, plus scope creep across 12 more. This is a repeat of a previously-known gap (#202) — it did not regress from a fix, it simply has never been fixed. The only reliable check was `git diff origin/main --stat` run directly inside the job's own worktree.
**TPM implication:** the TPM loop's "did the dispatched job produce anything" check cannot use `synlynk jobs` output as ground truth. It needs to diff the job's worktree against its base branch directly, the same manual workaround used here.

### 2. Dispatch jobs can silently auto-create a GitHub PR
Discovered mid-session: pushing from inside a dispatch worktree (job-e2c331a5) auto-created PR #938 with a generic title (`fix: ## Permissions (job-e2c331a5)`) and boilerplate body, before any `gh pr create` was run. This wasn't documented anywhere Claude had visibility into — it was discovered only because a manual `gh pr create` failed with "a pull request already exists."
**TPM implication:** the loop's dispatch→PR step needs to treat "PR already exists" as an expected outcome to detect and reconcile (retitle/rewrite body), not an error path. If a TPM loop assumes it always creates the PR itself, it will either double-create or silently attribute the wrong title/description to real work.

### 3. Version-bump release breaks a hardcoded test, silently gates on the wrong signal
`tests/test_synlynk.py::test_version_is_0120` asserts `synlynk.VERSION == "0.13.0"` literally — so every version bump fails exactly one test by design, and that failure has to be manually recognized as "expected, not a regression" rather than blocking. Observed as `1 failed, 1381 passed` during the v0.13.1 release verification pass.
**TPM implication:** if a TPM loop gates release verification on "tests pass," this test will produce a false-negative on every single release cycle unless the loop knows to special-case it (or the test itself gets fixed to check `VERSION` is well-formed rather than pinned to a literal string — worth a follow-up issue on its own).

### 4. Shared GitHub bot identity blocks self-review approval (#423)
All dispatched agents share one GitHub identity, so `gh pr review --approve` on a dispatch-authored PR always fails with "Can not approve your own pull request" — this is a structural GitHub-side constraint, not a bug, but it means "was this PR properly reviewed" cannot be read off `reviewDecision` alone; the sanctioned fallback (a formal COMMENT review with an approve checklist) doesn't set `reviewDecision: APPROVED` at all.
**TPM implication:** attribution/evidence tracking for "was this reviewed by someone other than the author" needs a review-discipline signal independent of GitHub's native `reviewDecision` field — e.g. parsing the COMMENT-review body for the approve-checklist pattern, or tracking it as a separate synlynk-side event.

### 5. `--requires-gh-write` can silently no-op
The flag can return exit 0 with no real work performed when no role-scoped GitHub App token is provisioned — a job can report success while doing nothing. Standing memory already flags this; re-confirming it here because it's exactly the shape of attribution failure a TPM loop is most exposed to (success signal decoupled from actual effect).

## Prompt / process friction

These didn't produce wrong attribution, but each one cost manual intervention, context, or wall-clock time that a durable loop should absorb.

### 6. `gh pr merge --auto` unusable on this repo
Fails outright with "Auto merge is not allowed for this repository" — every merge this week required polling `gh pr checks --watch` and manually re-running `gh pr merge` once CI went green. A TPM loop doing autonomous merges needs either repo-setting changes (enable auto-merge) or a built-in CI-poll-then-merge step; today it's pure manual toil.

### 7. `gh pr merge` requires a determinable branch context
Fails with "could not determine current branch: failed to run git: not on any branch" when run from a detached-HEAD dispatch worktree — has to be re-run from a location with a real branch (the primary repo root). Minor, but it's exactly the kind of environment-shape assumption that breaks silently in an unattended loop.

### 8. Unexplained local-file-edit-persistence quirk
A local, uncommitted edit (fixing an unrelated pre-existing YAML bug purely to unblock a build smoke-test) verified as applied via direct readback, then reverted itself before the next command ran, with `git status --short` showing a fully clean tree throughout — no error, no visible cause. Not diagnosed; documented here because if this recurs inside an unattended TPM loop it would look like a job silently losing its own work with zero error signal.

### 9. Scope creep inside dispatched jobs isn't self-flagged
Agy's job-e2c331a5 made trivial, unrequested YAML-quoting edits to 12 unrelated blog files alongside its two intended files. Nothing in the job's own output flagged this as out-of-scope — it was only caught by a manual `git diff origin/main --stat` review before the PR was cleaned up. A TPM loop doing unattended dispatch needs an automated scope-diff check (intended files vs. actually-touched files) rather than relying on a human reviewer catching it every time.

### 10. Recurring historical friction (already tracked, re-confirmed present)
Two items already in standing memory recurred or were re-confirmed this week rather than being new:
- **Grok wrong-branch dispatch bug** — occurred twice across the arc; Agy remains the confirmed reliable fallback for headless `gh` writes.
- **GEMINI.md stale-revert (#884/#899)** — marked fixed via PR #894, recurred same-day in a different worktree; filed as #899, still not confirmed resolved as of this report.

These aren't new findings but are worth carrying into the TPM design explicitly: a durable loop needs retry/fallback routing for harness-level failures (Grok → Agy) as a first-class behavior, not an ad hoc human decision each time.

## Summary for TPM/session MVP design

The clearest single pattern across all ten findings: **every automated "this succeeded" signal observed this week (job summary, PR auto-creation, test suite, GitHub review decision, `--requires-gh-write` exit code) had at least one way to be true while the real state was false, empty, or wrong.** The manual loop only worked because a human re-verified against ground truth (`git diff`, direct `gh pr view`, direct file reads) at every step. The TPM/session MVP's checkpoint-reconciliation work should treat "verify against the actual artifact, not the tool's self-report" as a base design requirement for every step in the closed loop, not an edge case to handle later.
