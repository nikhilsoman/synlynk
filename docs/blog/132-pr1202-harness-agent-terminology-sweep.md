# PR #1202 — Saying What We Mean: Harness vs. Agent

## Where we left off

The previous #1198 sub-issue, #1200 (doctor check for elevated PR review cycles), shipped as PR #1245 — the second of five sub-issues in the Autonomous Operations Activation tracking arc to close, after #1201. With #1200 done, the remaining three unstarted sub-issues were #1199 (charter corpus-reference docs), #1202 (harness/agent terminology standardization), and #1203 (GOVERNS backlog automation, which needs its own brainstorm pass first per the issue text). #1202 was picked next: its own issue text noted it needed "a decision before any rename sweep is dispatched" — but that decision had already been made. `docs/glossary-agent-vs-harness.md` already defines the split canonically: **Agent** is a persistent role identity with a charter (pm/architect/tpm/dev/designer/qa/marketing/synlynk-bot) — *who* is accountable; **Harness** is a swappable execution backend (Claude/Agy/Codex/Grok/local) — *how* work gets executed. The prerequisite #1202 asked for was satisfied before the ticket was even picked up.

## What moved the goalpost

Nothing strategic shifted here — this was a scoping call, not a redirect. The plan (`docs/superpowers/plans/2026-08-29-harness-agent-terminology-sweep.md`) locked the sweep to prose only: `help=` strings, docstrings, and `#` comments in `synlynk/*.py`, wherever the text used "agent" to mean an execution backend or "harness" to mean a role identity. Two things were explicitly carved out:

- **CLI subcommands, flags, and DB columns** — `synlynk agent configure`, `--agent`, `--as-agent`, `known_agents`, DB `agent` columns. Renaming those is a breaking change with a real deprecation-path cost; that decision got its own follow-up issue (#1255) rather than being bundled into a prose PR.
- **Historical proposal docs** (`docs/*-human-agent-hybrid-workgroup-study.md`, `docs/multi-agent-orchestration-proposal.md`) — left untouched on the same principle already applied to not backfilling PR #1233's missing blog post: rewriting history to match later terminology misrepresents it.

## What this PR shipped

Two dispatched Codex jobs swept ten files across two tasks — `cli.py`/`dispatch.py` first, then `__init__.py`, `capability_sweep.py`, `costs.py`, `db.py`, `jobs.py`, `probe.py`, `quota.py`, `wizard.py` — rewording roughly 25 lines total. Every change stayed inside a string literal or comment; no identifier, flag name, subcommand name, or DB key was touched, verified line-by-line against `git diff` rather than trusted from the job's own report.

The two-stage review (spec-compliance, then code-quality) required by the subagent-driven-development workflow caught two real gaps that a first-pass dispatch missed:

- **Spec-compliance review** found 8 `cli.py` help strings the Task 1 re-scan step should have caught but didn't — several directly inconsistent with sibling files the same PR had already fixed (`jobs.py`'s handoff docstring said "harness," but the paired `cli.py --stalled`/`handoff` help text still said "agent"; same for `db.py`'s credit-grant docstring vs. `cli.py`'s `credit grant` help). Fixed in a follow-up commit.
- **Code-quality review** found two matched-pair inconsistencies in `synlynk/quota.py` — docstrings where three of four references to the concept were swept to "harness" but one word in the same sentence was missed, producing agent/harness whiplash mid-paragraph. Fixed in a second follow-up commit.

Both follow-ups were small enough to be tempting to hand-edit directly, but went through `synlynk dispatch` anyway, per the locked role split — implementation stays out of Claude's hands even for two-word fixes.

Test baseline held steady across all three commits and the final rebase onto `origin/main`: `2 failed, 2312 passed, 2 skipped`, matching the long-standing pre-existing `sqlite3.OperationalError: database is locked` flakes in `test_agent_quota_tracking.py` and `test_roles.py` — zero regressions from a pure prose sweep, confirmed by an independent rerun in the properly cleaned worktree rather than trusting either dispatch job's self-reported (and sandbox-noisier) test count.

One dispatch-tooling snag repeated from the #1200 work: `_task_requires_gh_write()`'s false-positive heuristic (already filed as #1246 from that prior session) tripped again on the first dispatch attempt here, this time on the task prompt's own mentions of "gh#1202" and "review." Worked around by passing `--role dev` explicitly rather than reformulating the prompt, since #1246 is now tracked separately and doesn't need re-diagnosing each time it recurs.

## Where this leaves the long-arc goal

#1198's tracking arc now has three of five sub-issues closed (#1201, #1200, #1202). #1202 also spawned its own follow-up, #1255, tracking the harder breaking-change decision (CLI flag and DB column renames) that #1202 deliberately deferred. Remaining unstarted: #1199 (charter corpus-reference docs) and #1203 (GOVERNS backlog automation, brainstorm-gated).

## New goalpost

Land this PR, run Worktree Hygiene Protocol cleanup on `feat/1202-harness-agent-terminology-sweep` and its now-already-cleaned dispatch sub-worktrees, then pick up the next #1198 sub-issue — #1199 or #1203, with the choice surfaced explicitly rather than assumed, matching how #1200 and #1202 were each chosen with reasoning shown rather than picked silently.
