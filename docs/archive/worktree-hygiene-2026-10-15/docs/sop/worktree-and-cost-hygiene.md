# Worktree Hygiene, Cost Capture & Cost Visibility

> Moved out of root `CLAUDE.md` (2026-10-13, context-window-optimization plan) — same content, loaded on demand instead of resident in every session's root instruction file.

## Cost Capture Protocol

**For every PR, before merging:** confirm all dispatched/wrapped work in this PR is auto-captured (nothing to do — it already is via `dispatch_agent()`/`synlynk exec`), and any native/PM-session work (brainstorming, design docs, manual fixes) not tied to a dispatched job has a corresponding `synlynk cost log` entry. If genuinely zero cost was incurred outside dispatched work, note that explicitly in the PR rather than skipping the check silently.

For native/interactive provenance, record the PR directly with `synlynk cost log --pr <pr-number> --harness <harness>`; dispatched work should continue to use `--job-id`.

`synlynk release` sessions use `synlynk cost log` the same way — there is no automatic capture for native CLI invocations of `gh release create` / release tooling.

Enforced by discipline (Claude/PM checks it as part of PR housekeeping), not CI — matches how the Blog Post Protocol already operates. Not a blocking CI gate.

## Worktree Hygiene Protocol

**Clean up a worktree and its branch the moment the PR that owns them lands — same turn as the merge, not deferred.** This includes worktrees nested under a parent worktree (dispatch sub-jobs): when the parent's PR merges, sweep every nested `worktrees/job-*` inside it too, since their work was folded into the parent branch before merge.

1. **On merge (Option 1/finishing-a-development-branch, or a PR merge you perform directly):** remove the worktree (`git worktree remove`, `cd` to main repo root first) and delete the local branch (`git branch -d`). Delete the remote branch too if `git ls-remote --heads origin <branch>` shows it still exists.
2. **Before deleting anything:** confirm via `git status --short` in the worktree (no uncommitted changes) and via `git merge-base --is-ancestor <branch> origin/main` OR a matching `gh pr ... state: MERGED` (squash merges break literal ancestry — the PR state is the source of truth in that case). If neither confirms merge, do not delete — flag for review instead.
2a. **If a branch's content is genuinely unmerged and has no PR** (e.g., a design worktree that was set aside), do not silently discard it — archive it per the standing archive-before-branch-removal memory (copy to `docs/archive/<topic>/`, commit via its own small branch/PR) before removing the worktree.
3. **Periodic audit (at least every ~20 dispatched jobs, or when `synlynk status`/`synlynk jobs --all` starts feeling stale):** run a full sweep — `git worktree list --porcelain`, cross-reference every branch against `gh pr list --state all` and `git merge-base --is-ancestor`, flag dirty worktrees for individual review, and report a safe/unsafe/needs-review breakdown before deleting anything in bulk.
4. **`synlynk probe` and other one-off diagnostic dispatches also create worktrees** — treat their output the same way: if the job made no real changes (`files: 0 touched`, zero diff vs. `origin/main`), clean up the worktree/branch immediately rather than letting it linger as one more stale entry.

Rationale: a July 2026 audit found 30 stale worktrees/branches accumulated because cleanup was only ever done reactively, in large batches, long after the underlying PRs had merged. This protocol front-loads that cost onto the merge step where the context is already loaded, instead of letting it compound into a periodic manual archaeology exercise.

## Cost Visibility
1. Log estimated_cost in the job context header before dispatch.
2. Check `synlynk status` for current burn rate.
3. Confirm all work is captured via telemetry and manual/PM work is logged via `synlynk cost log`.
4. Append actual cost to `project-docs/costs.md`.
5. **Reviewer-logged cost provenance backfill (gh:#2071, 2026-10-06).** If a reviewer sees the missing-provenance stderr hint (from `_emit_missing_provenance_hint`) or `synlynk pr check` reports "no implementing job provenance found for PR #N", backfill a `cost_entries` row before re-running `pr check`. `--tokens-in`/`--tokens-out` are required by the CLI — pull the implementing job's actual token counts from its dispatch estimate/actual line (`synlynk logs --job <job-id> | grep "dispatch estimate" -A2`, or the job's own completion summary) rather than guessing:
   ```
   synlynk cost log --pr <N> --harness <implementer-harness> --tokens-in <in> --tokens-out <out> --job-id <job-id> --note "logged by reviewer, see design spec 2026-10-06"
   ```
   Re-run `synlynk pr check` after logging. Only escalate to a manual `--admin` override if the backfill itself fails or the implementer harness/model genuinely cannot be determined (e.g. no `dispatch/<harness>/job-<id>` branch naming and no native-session record) — do not jump to `--admin` as the first response to a missing-provenance hint.
