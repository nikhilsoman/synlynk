# Session Handoff — 2026-11-14 — LIVE-31 incident, remediation, and cleanup

**From:** Claude (Home Conductor / PM role, this session)
**To:** Agy — resuming in Home Conductor (Mode A, PM/TPM/Architect) mode
**Worktree:** `/Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+live-31-rca` (branch `chore/live-31-rca`)
**Scope note:** This covers everything from this session's handoff point through the present moment, in chronological order, including every document, issue, PR, and dispatched job touched. All GitHub-write actions below were performed either by dispatched headless jobs under role identities, or by this interactive session using `synlynk gh --role <role> -- ...` / `SYNLYNK_GH_ROLE=<role> git push` — never raw `gh`/personal identity, per the Hardened PR Review Policy and the LIVE-31 incident itself (see below).

---

## 1. LIVE-31 incident — discovery and root cause

A dispatched review job (`job-04d8e2b4`, codex, role qa) reviewing **PR #5248** (`fix(tpm): close release-proposal loop regression`, gh:#5246) posted a `CHANGES_REQUESTED` review by calling raw `gh pr review` instead of the project's `synlynk gh --role <role> -- ...` wrapper. The sandbox inherited the host's already-authenticated personal GitHub CLI session, so the review landed under the operator's personal identity (`nikhilsoman`), not a role/bot identity.

This was originally an attribution/audit-trail violation, but it surfaced a second, concrete consequence during remediation: **the stale personal-identity review actively blocked a later, fully-approved, CI-green merge** of PR #5248, because GitHub branch protection evaluates `reviewDecision` per distinct reviewer — a later, different reviewer's APPROVED does not supersede an earlier reviewer's outstanding CHANGES_REQUESTED.

**Root cause (two layers):**
1. `synlynk gh --shim-env` intercepts `git`'s HTTPS credential path (refuses `push` without a role token) but does **not** intercept raw `gh <write-command>` calls — those fall through to whatever `gh auth status` the sandbox's inherited shell resolves to.
2. GitHub's `reviewDecision` is computed per-reviewer; a stale personal-identity review from gap (1) remains an independent outstanding block indefinitely until explicitly dismissed/superseded from that same identity.

## 2. PR #5248 remediation

- Round-2 review (`job-04d8e2b4`) correctly found a real blocking issue (`tests/test_events.py::test_approval_tickets_table_exists` out of sync with a new `constituent_story_ids` column) but posted it under the personal identity (the bug above).
- Round-2 fix (`job-a5426cf6`) fixed the flagged issue.
- Round-3 review (`job-ac454d19`, role qa) correctly posted `APPROVED` under role identity `synlynk-synlynk-qa`.
- First merge attempt (`job-315ff7f5`, role qa) **failed**: `Pull request nikhilsoman/synlynk#5248 is not mergeable: the base branch policy prohibits the merge.` The job correctly refused to force-merge and reported the exact failure.
- Direct inspection (`pr view --json reviewDecision,mergeStateStatus`) showed `reviewDecision: CHANGES_REQUESTED` / `mergeStateStatus: BLOCKED` despite the latest review being APPROVED — the round-2 personal-identity review (REST id `5900723225`) was still outstanding.
- Surfaced to Nikhil via AskUserQuestion; he chose explicit remediation over self-dismissal or `--admin` override: dismiss via GitHub REST API under the `qa` role identity:
  ```
  synlynk gh --role qa -- api --method PUT repos/nikhilsoman/synlynk/pulls/5248/reviews/5900723225/dismissals -f message="..."
  ```
  `reviewDecision` flipped to `APPROVED`, `mergeStateStatus` to `CLEAN`.
- Merge re-dispatched (`job-c1c77134`, identical brief) and **succeeded**: merge commit `25806322e32d1ec99e7b3044262eef84c60c8598`, `mergedBy: app/synlynk-synlynk-qa` (role identity, confirmed independently just now via `pr view`). Issue #5246 auto-closed via `Fixes #5246` linkage.
- Worktree Hygiene Protocol swept all 8 nested dispatch worktrees belonging to this PR's chain (`job-71288d2f`, `job-a5426cf6`, `job-ac454d19`, `job-315ff7f5`, `job-c1c77134`, `job-04d8e2b4`, `job-520ba6b8`, `job-ee4f1ff0`) — all confirmed clean, subsumed, removed; no remote branches existed for any.

## 3. RCA document and tracking issues filed

**Document written:** `docs/rca/2026-11-14-LIVE-31-dispatched-job-raw-gh-personal-identity.md` (Sev1 RCA). Covers: summary, timeline, root cause, impact, "why existing guardrails didn't catch it," action items, prevention, resolution status. **Status in the doc: root cause confirmed; mitigated per-incident for PR #5248; structural fix not yet shipped.**

**Issues filed from this incident (all confirmed OPEN via live `gh issue list` just now):**
| # | Title |
|---|---|
| [#5249](https://github.com/nikhilsoman/synlynk/issues/5249) | `[LIVE-31] Dispatched jobs can post GitHub writes under personal host identity via raw gh CLI, bypassing the shim` — the structural fix tracking issue (Action Items 1–2 of the RCA) |
| [#5250](https://github.com/nikhilsoman/synlynk/issues/5250) | `policy.json role_task_type_compat.qa missing "merge" despite merge_authority.can_merge granting qa merge rights` — adjacent policy-config gap found during remediation |
| [#5251](https://github.com/nikhilsoman/synlynk/issues/5251) | `synlynk pr check / policy check-merge should flag a stale personal-identity review as actionable (LIVE-31 action item 3)` |
| [#5252](https://github.com/nikhilsoman/synlynk/issues/5252) | `Audit open PRs for latent stale personal-identity reviews (LIVE-31 action item 4)` |

None of these are shipped/closed yet — they are the real follow-up work this incident generates. **Agy should treat #5249, #5251, #5252 especially as live backlog items**, not just historical record (#5250 is a smaller adjacent fix).

## 4. PR #5253 — committing and shipping the RCA doc itself

- Dispatched job `job-8f982105` (codex) committed the RCA doc (commit `23ce7237...`) and opened **PR #5253** (`docs(rca): LIVE-31 — dispatched job posted GitHub review under personal identity via raw gh`).
- **User instruction: "Assign a reviewer and run synlynk pr check on it."** Dispatched a reviewer job; the dispatcher rerouted the requested `claude` harness to `agy` ("routing selected 'agy'; the capability probe did not reject 'claude'") — this still satisfies the cross-harness+model review requirement since codex (implementer) ≠ agy (reviewer). Job `job-f2e51af1` (agy):
  - Cross-checked the RCA's claims against live GitHub state for #5249/#5250/#5251/#5252 and PR #5248 — all matched, "Discrepancies found: None."
  - Ran `synlynk pr check` — initially flagged `[OBSERVE MODE — not blocking] no implementing job provenance found for PR #5253` (missing cost-log entry for the implementing job).
  - Posted `APPROVED` via `synlynk gh --role qa -- pr review ...` (not raw gh), independently confirmed via `pr view --json reviews` under identity `synlynk-synlynk-qa`.
- **Cost Capture Protocol backfill** (performed by this session, since `pr check` flagged missing provenance): pulled job-8f982105's actual token usage from its own completion log and logged it:
  ```
  synlynk cost log --pr 5253 --harness codex --tokens-in 475239 --tokens-out 4485 --job-id job-8f982105 --note "backfill by reviewer, docs-only LIVE-31 RCA PR"
  ```
  Re-ran `synlynk pr check` — fully green: `✓ Cross-harness review passed — implementation codex / o4-mini (dispatch metadata) reviewed by agy / gemini-3.8-flash-medium (dispatch metadata)`, `✓ PR check passed — all model versions attested.`
- **User instruction: "Merge it."** Per the project's merge-execution rule (reviewer's own dispatched job performs the merge, not the interactive PM session — RCA'd 2026-10-09, PR #2149, to avoid the interactive auto-mode classifier nondeterministically denying an already-cleared action), dispatched `job-166374ea` (agy, role qa):
  - Independently re-confirmed `reviewDecision: APPROVED`, `mergeStateStatus: CLEAN`.
  - Ran `synlynk policy check-merge --role qa` → cleared (exit 0).
  - Detected the repo only allows squash merges (`mergeCommitAllowed: false`, `squashMergeAllowed: true`) and correctly adapted from the brief's `--merge` to `--squash`, disclosing this explicitly rather than silently deviating.
  - Merged via `synlynk gh --role qa -- pr merge 5253 --squash`. **Merge commit `6cd36ee40451819000fa24d72feba2207ac4295b`, `mergedBy: app/synlynk-synlynk-qa`** — independently re-verified by this session via direct `pr view`.

## 5. Worktree Hygiene Protocol sweep — PR #5253's chain

Per CLAUDE.md's Worktree Hygiene Protocol ("same turn as the merge... every nested `worktrees/job-*`"):
- Identified 3 nested worktrees under `.claude/worktrees/chore+live-31-rca/worktrees/`: `job-8f982105` (`dispatch/codex/job-8f982105`), `job-f2e51af1` (`dispatch/agy/job-f2e51af1`), `job-166374ea` (`dispatch/agy/job-166374ea`).
- Confirmed all three clean (`git status --short`, no output) before touching anything.
- Removed all three worktrees (`git worktree remove`), deleted all three local branches (`git branch -D`), confirmed via `git ls-remote --heads origin <branch>` that **none** had remote counterparts — nothing further to delete.

## 6. Parent worktree found dirty — new cost-archive PR

The parent `chore+live-31-rca` worktree itself was **not clean**: staged modifications to `project-docs/archive/.costs-archive.cursor` and `project-docs/archive/costs-2026-H11.md` (auto-generated cost rollup files, pre-existing at session start, unrelated to PR #5253's content). Per the Worktree Hygiene Protocol's safety check, did **not** delete a dirty worktree silently — flagged to Nikhil instead.

**User instruction: "Commit those cost-archive changes, then remove the worktree."**
- Committed as `dc1358ae` ("docs: sync cost archive rollup").
- Realized this commit was now on a branch whose PR (#5253) had already merged, and no remote copy existed — deleting the branch would silently lose it. Flagged via AskUserQuestion with three options (push+PR / cherry-pick to fresh branch / discard as regeneratable).
- **User chose: "Push branch, open small chore PR."**
- `git push` was refused by the synlynk gh shim (`host identity is not used`) — retried as `SYNLYNK_GH_ROLE=pm git push -u origin chore/live-31-rca`, succeeded.
- Opened **PR #5254** (`docs: sync cost archive rollup`, base `main` ← `chore/live-31-rca`) via `synlynk gh --role pm -- pr create`, GOVERNS-linked to `story-d2fabc52` / `goal-eacab0dc` (reused from the LIVE-31 work this commit surfaced from).
- Dispatched a cross-harness reviewer: first attempt failed preflight (`Harness 'agy' would dispatch headless with read-only permissions, which is a known auto-denial pattern`); retried with `--requires-gh-write --gh-write-target-kind pr --gh-write-expect review_posted`, which succeeded → **job-33dd37ab** (agy, rerouted from requested `claude`).
- **job-33dd37ab just completed successfully:**
  - Confirmed diff scoped strictly to the two archive files, 0 code/behavior changes.
  - Ran `synlynk pr check` — green except one non-blocking observe-mode warning: no implementing-job cost provenance found for PR #5254 (expected — this commit came from an interactive session, not a dispatched job).
  - Posted `APPROVED` via `synlynk gh --role qa -- pr review ...`, independently confirmed under role identity `synlynk-synlynk-qa` (not personal).
  - Ran the verification suite: 81 passed in 9.02s.
  - **Did not merge** (review-only brief, correctly honored). Cost: $0.45 (85,288 in / 13,064 out).

## Current state (as of this report)

| Item | Status |
|---|---|
| PR #5248 | **MERGED** (`25806322`), role identity, issue #5246 auto-closed |
| PR #5253 (LIVE-31 RCA doc) | **MERGED** (`6cd36ee4`), role identity |
| PR #5253's 3 nested worktrees/branches | Swept — removed, no remote remnants |
| gh:#5249, #5250, #5251, #5252 | **All still OPEN** — real backlog, not yet actioned |
| PR #5254 (cost-archive sync) | **OPEN, APPROVED** by `synlynk-synlynk-qa`, `pr check` green (one non-blocking observe-mode cost-provenance warning) — **not yet merged** |
| Cost provenance for PR #5254 | **Not yet backfilled** — `synlynk cost log --pr 5254 --harness claude --tokens-in <n> --tokens-out <n>` should be logged for this interactive-session commit before/independent of merge, per the Cost Capture Protocol's native-session provenance rule |
| Parent worktree `chore+live-31-rca` / branch | **Still exists**, now clean (commit `dc1358ae` pushed) — not yet removed; should be swept once PR #5254 merges, same discipline as above (confirm clean, confirm merged via PR state since squash merges break literal ancestry, remove worktree, delete local branch; remote branch `chore/live-31-rca` does exist now on origin post-push, so that will need deleting too — check `git ls-remote --heads origin chore/live-31-rca` before assuming not) |

## Immediate next steps for whoever resumes (Agy)

1. Log cost provenance for PR #5254 (native/interactive session, harness `claude`), then optionally re-run `synlynk pr check` to clear the observe-mode warning (non-blocking, so this can also just be done for hygiene).
2. Merge PR #5254 the same way PR #5253 was merged: re-verify `reviewDecision`/`mergeStateStatus` directly, run `synlynk policy check-merge --role qa`, merge via the reviewer's own dispatched job (`synlynk gh --role qa -- pr merge 5254 --squash` — this repo is squash-only), never from the interactive/conductor session directly.
3. Sweep the parent `chore+live-31-rca` worktree and both local and remote `chore/live-31-rca` branches once #5254 is confirmed merged.
4. The real unfinished work from this whole incident is **issues #5249, #5251, #5252** (the structural fixes) — #5250 is a smaller adjacent policy-config fix. These are backlog, not closed by anything done this session; RCA's own "Resolution Status" section explicitly says mitigation was per-incident only, structural fix not shipped.
