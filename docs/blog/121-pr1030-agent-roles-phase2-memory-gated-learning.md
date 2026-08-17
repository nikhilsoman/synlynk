# PR #1030 — Agent-Roles-Charters Phase 2: Making Capability Grants Mean Something

## The Goal at the End of the Previous PR

PR #1022 (post #120) closed out Phase 1's follow-up debt: `capability_grants` now survives a
charter edit instead of being wiped, and `daemon_jobs.agent_id` is persisted so a dispatched job's
originating workspace agent is no longer thrown away the moment `dispatch_agent()` returns. That
PR's own closing line named the next goalpost explicitly: Phase 2 means making `capability_grants`
*load-bearing* — actually read and enforced during dispatch/harness selection — and building a
gated-learning/memory layer on top of the identity and persistence foundation Phase 1 finished
laying.

## Strategic Shift in This PR

None from the approved spec (`docs/superpowers/specs/2026-08-17-agent-roles-phase2-memory-gated-learning-design.md`),
but one correction surfaced mid-execution and is worth naming: Task 2's plan draft assumed `"agy"`
would win the alphabetical-first static-baseline pick for the `"architect"` org role. Before
re-dispatching, I live-verified `AGENT_CAPABILITY_BASELINES` directly — `agy`'s roles are
`['builder', 'verifier']`, not `['architect', ...]` — so the actual winner is `"claude"` (the first
`CORE_FLEET` name, sorted, that's actually tagged `"architect"`). Fixed three test assertions in the
plan file itself (committed as `70a2938`) before dispatching, rather than letting a Codex
implementer discover the mismatch and burn a NEEDS_CONTEXT round-trip on it.

## What This PR Shipped

Executed as 4 implementation tasks (plus a full-suite verification task) via Subagent-Driven
Development, each code task dispatched individually to Codex
(`synlynk dispatch codex --task "..." --force-agent --context-mode full`), diff-inspected and
test-verified directly in each task's nested dispatch worktree before merging — never trusting a
job's self-reported "DONE" status alone:

- **Synthetic per-org-role story mechanism** — a new `_role_dispatch_story_id(org_role)` helper
  (`_constants.py`) computes a stable placeholder ID (`__role_dispatch_<role>__`), and
  `_ensure_role_dispatch_story()` (`jobs.py`) lazily `INSERT OR IGNORE`s a matching row into
  `stories`, mirroring the existing `_seed_capability_ledger_from_baseline` pattern so role-only
  dispatches (no real `story_id`) get a stable key to accrue a learned capability signal against.
- **Read path** — `resolve_dispatch_harness()` (`dispatch.py`) now checks the synthetic-story score
  via `_best_agent_for_story()` before falling through to the static `_harness_for_org_role` pick,
  for role-only dispatches with a resolvable `org_role`. Stays side-effect-free (no DB writes, no
  subprocess) since `--dry-run` depends on that guarantee.
- **`static_baseline` escape hatch** — new `static_baseline: bool = False` parameter on
  `resolve_dispatch_harness()`, threaded through `dispatch_agent()` and a new `--static-baseline`
  CLI flag (mirrors how `--force-agent` is already wired end to end), plus through the `--dry-run`
  preview branch. When set, skips the synthetic-story lookup entirely — useful for forcing the
  deterministic pick when you don't want a stale learned score influencing routing.
- **Write path** — `_write_capability_rating()` (`jobs.py`) now resolves `org_role` from
  `job.get("resolved_agent_role")` when `story_id` is empty, computes the synthetic story_id, and
  writes a `capability_ratings` row against it — so the learned signal this PR's read path consumes
  actually gets populated by completed role-only jobs, not just theoretically available.
- **Isolation invariant, enforced and tested** — the synthetic story_id never touches
  `daemon_jobs.story_id` or any other job-persistence field; a dedicated regression test
  (`test_role_only_job_never_persists_synthetic_story_id_to_daemon_jobs`) locks this in.

One accepted implementer deviation: Task 3's diff added an `engg_domain="general"` field to the
synthetic story's INSERT (not in the original dispatch instructions) and an `if not org_role:`
guard around `_normalize_capability_tags`. Investigated rather than reflexively accepted — the
`stories` table already defaults `engg_domain` to `'backend'`, so the original plan text wasn't
broken, but the addition makes the synthetic story's tag fields internally consistent with the
other "general" placeholders. Judged a legitimate correction, not scope creep, and confirmed via
the full specified regression run (221 tests) before merging.

Full suite: **2038 passed, 2 skipped, 0 failed** (`python3 -m pytest -q`), plus a live CLI spot-check
— registered a fresh `dev`-role workspace agent with zero prior rating history, ran
`synlynk dispatch --as-agent <id> --task "..." --dry-run`, and confirmed the cold-start path
resolves to a concrete harness (`agent: agy`) rather than `agent: None`.

## Brainstorm Visuals Used

None — this extends an already-mapped file neighborhood (`dispatch.py`, `jobs.py`, `cli.py`,
`_constants.py`) with a mechanism (synthetic placeholder rows mirroring a real ledger pattern) that
didn't need visual exploration to reason about.

## What This Achieved on the Path to Autonomy

Capability-based routing has, until now, only worked for dispatches with a real `story_id` — a
role-only dispatch (`--as-agent dev`, no story) always fell straight through to the static
alphabetical baseline, with no way to learn "this org role's dispatches keep landing well on
Codex" over time. This PR closes that gap: role-only dispatches now accrue and consume the same
learned signal that story-driven dispatches already benefit from, while the `static_baseline` flag
keeps the deterministic fallback available whenever a caller explicitly wants to bypass learning
(useful for cold-start diagnostics or deliberately resetting routing behavior).

## The Goal at the End of This PR

`capability_grants` is now load-bearing for role-only dispatch, not just persisted. The next
goalpost, per the two gaps this PR's own design doc left explicitly out of scope: a
"jobs by agent" view / cost attribution built on `daemon_jobs.agent_id` (persisted since PR #1022,
still unconsumed), and actual enforcement of `capability_grants` restrictions during harness
selection (this PR adds *learned scoring*, not *grant enforcement* — a role can still be routed to
any `CORE_FLEET` harness regardless of what its grants explicitly permit).
