---
title: "PR #328 — Live Command Selftest: Does synlynk Actually Work in a Real Repo?"
date: 2026-07-18
series: "Building the OS for Multi-Agent Development"
post: 68
pr: "#328"
merged: 2026-07-18
---

## The Broader Goal at the End of the Previous PR

PR #292 closed out model-identity correctness — Tier-2 probes stopped collapsing three of four agents into `model_version='unknown'`. With v0.12.0 (Measurement & Reliability) shipped and its immediate follow-on fixed, the GTM checklist's item 2 (SDLC/GOVERNS stage placement) was already fully shipped via the command taxonomy PRs (#303, #316, #319). Item 1 remained open and unscoped: "Deep review of every synlynk command and its testing in a live repo scenario." Every command had unit tests under mocks. None had ever been proven to actually work end-to-end against a real, live host repo — the taxonomy work built the map (59 commands, GOVERNS stages, capability tiers) but never drove a car across the terrain it described.

## Strategic Shifts in This PR

None to the scope as brainstormed. The design (`docs/superpowers/specs/2026-07-17-live-command-selftest-design.md`) explicitly bounded the work to avoid a 59-command bespoke-scenario slog: a generic `--help` fallback scenario covers every taxonomy command by default, with hand-written real scenarios layered on only for (a) the core first-session lifecycle commands a new user actually touches, and (b) the four paid-agent-CLI commands (`dispatch`, `exec`, `schedule --execute`, `release`) that need budget-capped guardrails rather than a bare fallback. Anything beyond that — more bespoke scenarios, deeper live coverage — was explicitly deferred as follow-up, not squeezed into this plan.

## What This PR Shipped

A new `synlynk/selftest.py` module (794 lines at merge) wired as a `selftest` CLI subcommand, dry by default with a `--live` flag capped at $2 real spend:

- **`ScenarioContext`/`ScenarioResult` dataclasses** and a `SELFTEST_SCENARIOS` registry keyed by taxonomy command name, driven by `COMMAND_TAXONOMY` (59 entries) with a generic fallback scenario for any command without a bespoke entry.
- **`run_selftest(live=False)`** iterates the full taxonomy sorted by a dependency-aware `_selftest_sort_key`, executes whichever scenario is registered (or the fallback), and aggregates results.
- **Bespoke lifecycle scenarios** for `init`, `scan`, `join`, `goal create/list/link/status`, `story create/list`, `decide`, `dispatch`, `jobs`, `status`, `instructions status` — the commands a new user's first real session actually exercises.
- **Budget-capped paid-command scenarios**: `_dispatch_scenario`, `_exec_scenario`, `_schedule_scenario` each check `ctx.remaining_budget() <= 0` before spending a cent, fire a trivial `"Reply with the single word OK and do nothing else."` prompt against the real agent CLI, and record actual/estimated cost against the cap. `_release_scenario` is a hard, permanent skip — release is a real-world publish action (git tag/push, GitHub release) with no safe way to run it against a scratch repo, so it's verified structurally via `--help` only, not exercised live.

**Delivery took four dispatch attempts for the paid-scenario task alone** — the most dispatch-heavy single task this project has needed. Attempts 1–2 failed outright; attempt 3 (job-1769d38d) correctly integrated prior work but then stopped without writing any new code, a "did the setup, reported done" failure mode distinct from the earlier two. Attempt 4 succeeded only after switching to an extremely prescriptive prompt — exact code embedded verbatim, an explicit "Step 0 is setup, not the task" warning, and a hard completion-check gate the job had to pass before it could consider itself finished. Even then, the successful commit bundled two unrelated file changes (`GEMINI.md`, `project-docs/todo.md`) that turned out to be a stray worktree-local `state.db` regenerating those files as a side effect of running ordinary `synlynk` commands inside the job's worktree — filed as issue #330. The fix was to cherry-pick only the single real commit, not the job's full worktree state.

**Post-merge, code review surfaced two real bugs** rather than nitpicks. Dispatched Grok as reviewer (job-4af48bb2 first attempt hit a headless permission auto-denial — Agy's baseline has no auto-approval flag equivalent to Grok's `required_flags: ["--always-approve"]`, so a tool permission prompt got silently auto-denied in headless mode; $0.39 spent for zero usable output, filed as issue #332 alongside the Grok-login gap from an earlier session). The retry (job-203ff24a) succeeded and posted two blocking findings directly on the PR: **B1** — the `--live` paid scenarios ran against the host repo's actual CWD instead of an isolated scratch workspace, contradicting the design's throwaway-repo safety story; **B2** — the status scenario hand-rolled an incomplete `cycle_capability` table schema that crashed with `OperationalError: table cycle_capability has no column named verb_count` whenever it ran before any other scenario happened to initialize the real schema first.

Both were dispatched to Codex as a single fix (job-0bf7cdc6, commit `5e94632`): `run_selftest(live=True)` now creates the scratch workspace once up front and threads that same path through to every scenario, paid and lifecycle alike, with a real `git init` + minimal config/commit; the status scenario now seeds through the real `synlynk_pkg._get_db()` init path instead of a hand-rolled `CREATE TABLE IF NOT EXISTS`. Two new regression tests lock both fixes in (12 total in `tests/test_selftest.py`, up from 10). A second Grok re-review (job-814e12f2) confirmed both fixes independently — including standalone-executing the status scenario to prove B2 doesn't just rely on scenario ordering — and surfaced one further non-blocking residual (N6: `DB_PATH` still resolves to the host's central ledger even though CWD isolation is now correct, meaning a live run's paid scenarios still write `daemon_jobs` rows into the real project ledger rather than a scratch one) before giving an explicit approve.

## Brainstorm Visuals Used

None — this was a spec-driven plan (`docs/superpowers/specs/2026-07-17-live-command-selftest-design.md`) with no visual design questions; the interesting decisions were scope boundaries (fallback vs. bespoke, which lifecycle commands count as "first session") resolved through direct text questions during brainstorming.

## What This Achieved on the Path to Autonomy

GTM checklist item 1 now has a real, repeatable answer instead of an open question: every one of the 59 taxonomy commands has *some* live-repo verification (fallback `--help` check at minimum), the commands a new user actually touches on day one have real behavioral scenarios, and the four commands that spend real money have budget-capped guardrails before they're ever exercised outside of mocks. This PR also produced the most complete live case study yet of where the dispatch mechanism's own guardrails are thin: a job that "finishes" without doing the task, a job that silently gets auto-denied by a headless permission gate, worktree-local DB corruption, and a review comment that only persists because the reviewer was explicitly told to post it to `gh pr comment` rather than trust job-log durability. All four became filed, root-caused issues (#329–#332) rather than one-off annoyances worked around and forgotten.

## Strategic Note: The Goal at the End of This PR

The live-command-selftest building block is shipped and merged. Four issues are now filed and scoped for follow-up, none blocking further work: #329 (`synlynk cost log` doesn't write to `costs.md`), #330 (stray worktree-local `state.db` can corrupt `todo.md`/`GEMINI.md`), #331 (`daemon_jobs` reconciliation has no ground-truth git verification, unlike the now largely-dead legacy job store that does), and #332 (preflight dispatch has no check for agent auth/login state or headless permission-allow-rule presence — the exact two failure classes that surfaced live during this PR's own review dispatches). Also open, non-blocking: N6 from Grok's re-review (rebind `DB_PATH` to the scratch workspace for full `--live` isolation, not just CWD isolation). None of these are required before GTM checklist item 1 is considered addressed at the building-block level — they're the next round of hardening, tracked rather than silently absorbed.
