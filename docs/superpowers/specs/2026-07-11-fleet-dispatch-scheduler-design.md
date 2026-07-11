# Fleet Dispatch Scheduler ("synlynk schedule") — Design

**Date:** 2026-07-11
**Author:** Claude (PM/architect role)
**Tracks:** #141 (quota + optimizer) — the "optimizer design doc, no code" half of the
issue's assignment table, following the base quota matrix (PR #154, merged).
**Status:** Approved, ready for implementation planning.

## Problem

#141's base matrix (merged) gave synlynk quota-aware *single-task* routing:
`_best_agent_for_story()` now runs a 3-stage sequence (capability score → quota
headroom → cost) to pick the best agent for one story at a time. But the issue's
stated goal is bigger than that:

> synlynk should actively schedule and sequence dispatches to maximize total useful
> output across a user's variable per-harness quotas/limits within their workspace or
> account.

Single-task routing can't do this. If Claude is near its 5h ceiling but Codex/Agy/Grok
have headroom, and ten stories are all capability-eligible for Claude, calling
`_best_agent_for_story()` ten times in a row doesn't load-balance — it just picks
Claude ten times until quota independently blocks it, story by story, with no view of
the batch. There is also no signal today for "this story can't be scheduled right now
because every eligible agent is quota-exhausted" beyond a `None` return, and no gate
preventing an ungroomed story from being scheduled at all.

This design proposes `synlynk schedule`: a fleet-level scheduler that computes a
dispatch plan across all ready stories and all agents' current quota headroom in one
pass, reusing #139/#141's existing per-agent scoring and quota logic as building
blocks rather than replacing them.

## Existing infrastructure this builds on

- **`capability_scores`** (#139) — per (agent, coordinate) weighted score.
  `_capability_candidates_for_story()` already returns best-first candidates with
  fallback through progressively wider coordinates.
- **`agent_quotas`** (#141 base) — per-agent headroom by quota_type/unit.
  `_quota_status_for_agent()` already returns `ok`/`exhausted`/`unknown` with a
  documented non-hard-blocking degraded-mode contract.
- **`daemon_jobs`** — an existing queue table (`job_id, agent, task, story_id, status,
  priority, depends_on, ...`) with a working launcher, `_dispatch_ready_jobs()`, that
  handles priority ordering, dependency gating, and concurrency-limited launching. It
  currently has no agent-selection or quota-awareness — `agent` is fixed at
  enqueue time by whatever created the row.
- **`stories`** — the backlog (`status`, `priority`, `goal_id` FK to `goals`).
  Nothing today prevents an ungroomed, just-created story from being dispatched.

**Key architectural decision:** the scheduler does not replace or duplicate
`daemon_jobs`/`_dispatch_ready_jobs()`. It computes assignments and writes them into
`daemon_jobs`, then reuses the existing launcher. `stories` is the input (backlog),
`daemon_jobs` is the output (execution queue) — the two tables keep distinct roles.

## Objective function

Score for a candidate plan = **Σ (capability_score × story_priority)** over all
stories the plan successfully assigns within available quota headroom. This directly
reuses #139's capability scores and the stories table's existing `priority` column —
no new signal is introduced. Cost (#140) remains a tie-breaker within the existing
`_CAPABILITY_COST_TIE_GAP`, not a primary objective term — the goal is maximizing
capability-weighted throughput, not minimizing spend.

**v1 scope:** greedy assignment against a *current* headroom snapshot from
`agent_quotas`. It does not model `reset_at` timing or attempt bin-packing against
future window resets — see Future Work.

## Algorithm

For each `synlynk schedule` invocation:

1. **Candidate selection:** `stories WHERE status='open' AND readiness='ready'`
   (see Readiness Gate below), excluding any story with a `queued` or `running`
   `daemon_jobs` row, ordered by `priority ASC`.
2. **Retry filtering:** for each candidate, look up `daemon_jobs WHERE story_id=? AND
   status='failed'`. If the story has reached `MAX_STORY_RETRIES` (2) failed
   attempts, move it to the plan's `blocked: retry_exhausted` list and skip further
   processing. Otherwise, note which agents previously failed this story, to exclude
   from step 3 unless they're the only capability-eligible option.
3. **Capability candidates:** call `_capability_candidates_for_story()` (existing,
   unchanged) for the story's coordinate, then remove agents excluded by step 2
   unless doing so would leave zero candidates (in which case retry is allowed and
   flagged `retry: previously failed with <agent>` in the plan output).
4. **Quota gate:** for each remaining candidate agent, call
   `_quota_status_for_agent()` (existing, unchanged). Drop agents with
   `status == "exhausted"`. Among the rest, prefer non-degraded (`status == "ok"`)
   over `unknown` — same rule `_best_agent_for_story()` already applies.
5. **Cost tie-break:** reuse `_best_agent_for_story()`'s stage-3 logic (existing,
   unchanged) among near-tied candidates (gap ≤ `_CAPABILITY_COST_TIE_GAP`) to pick
   the winning agent.
6. **Fleet-level headroom accounting (new logic):** once an agent is assigned to a
   story in this pass, decrement that agent's *in-memory* working headroom (not the
   `agent_quotas` table — nothing is written until `--execute`) by the story's
   `estimated_tokens`. This is the one genuinely new piece of logic: it's what makes
   the pass a *fleet* scheduler instead of N independent single-story calls — a later
   story in the same batch can no longer be assigned quota an earlier story in the
   same batch already claimed.
7. **Blocked stories:** any story with zero eligible agents after steps 3–4 (all
   quota-exhausted, or no capability data at all) goes into the plan's
   `blocked: quota` (or `blocked: no_capability_data`) list rather than being silently
   dropped.
8. **Output:** an ordered list of `(story_id, agent, model, reasoning)`, sorted by
   `priority ASC` within each agent's run (preserves existing backlog ordering;
   optimal sequencing against reset timing is v2 — see Future Work), plus the
   `blocked` lists from steps 2 and 7.

Steps 3–5 are pure reuse of #139/#141 code — no changes to `_best_agent_for_story()`,
`_capability_candidates_for_story()`, or `_quota_status_for_agent()` are required by
this design. Step 6 is new and lives in the scheduler itself.

## Readiness gate

Today, any `stories.status='open'` row is instantly schedulable — nothing enforces
grooming discipline before a story reaches execution.

**v1 (this design):** new `stories.readiness` column, `TEXT NOT NULL DEFAULT 'draft'`
(additive migration, same pattern as #141 base's `agent_quotas` columns). Step 1 of
the algorithm requires `readiness='ready'` in addition to `status='open'`. Two new
commands:
- `synlynk story ready <story_id>` — flips `draft` → `ready`. Supports `--all` for
  bulk grooming sessions.
- `synlynk story draft <story_id>` — reverses it, for pulling a story back for rework.

`synlynk schedule` dry-run output includes a `Not ready (N stories in draft)` summary
line so the grooming backlog stays visible without cluttering the assignment table.

## Retry / reassignment policy

Neither `_reconcile_daemon_jobs()` nor anything else today moves a story out of
`status='open'` when a job is created or fails — a story stays `open` for its entire
lifecycle regardless of `daemon_jobs` state. This means a failed job's story is
*already* re-eligible for the next `synlynk schedule` run for free, via step 1's
"no queued/running `daemon_jobs` row" guard — no new requeue code is needed for basic
re-eligibility.

What's missing, and what this design adds (steps 2–3 above):
- **Don't immediately reassign to the agent that just failed** — excluded unless it's
  the only capability-eligible candidate, in which case the retry is explicit and
  flagged in plan output.
- **Retry cap** — `MAX_STORY_RETRIES = 2` (3 total attempts). Beyond that, the story
  surfaces in `blocked: retry_exhausted` instead of being silently retried forever,
  forcing a human look.
- **Recompute timing** — stays on-demand, consistent with the execution model below.
  No background trigger fires the instant a job fails. In practice, other commands
  (e.g. `synlynk jobs`) already call `_reconcile_daemon_jobs()` before a user
  typically runs `synlynk schedule` again, so the next run sees fresh state rather
  than stale `running` rows.

## CLI shape

```
synlynk schedule                  # compute + print plan, no side effects (default)
synlynk schedule --execute        # compute plan, write daemon_jobs rows, call
                                   # _dispatch_ready_jobs() once
synlynk schedule --max-stories N  # cap plan size (default: unbounded)
```

Dry-run output is a table: story_id · assigned agent · capability score · quota
headroom consumed · reasoning — followed by `Blocked (quota)`,
`Blocked (retry_exhausted)`, and `Not ready` sections where applicable.

`--execute` performs the same computation, then for each assignment either updates an
existing `queued` `daemon_jobs` row for that story (if one exists without a
quota-aware agent pick) or inserts a new row, then calls `_dispatch_ready_jobs()`
once so anything within the concurrency limit launches immediately. Remaining rows
stay `queued` for the next `synlynk daemon` poll tick or the next `--execute` run.

This is deliberately **on-demand only** — no new background process. synlynk has no
daemon-lifecycle infrastructure today beyond the existing `synlynk daemon` poll loop
that already drives `_dispatch_ready_jobs()`; adding an auto-triggering scheduler is
explicitly out of scope (see Future Work).

## Degraded mode

If quota data is unreadable for an agent (mirrors `_read_agent_quota_rows()`
returning `None`), the scheduler falls back to pure capability-score ranking for that
agent — the same non-hard-blocking rule `_best_agent_for_story()` already implements.
The plan output flags `quota: unknown (degraded)` next to that assignment so the
degraded state is visible rather than silently treated as full headroom.

## Testing approach

(Guidance for implementation — Grok/Codex own the build per the role split; no code
in this document.)

- Fleet-level headroom accounting: two stories both best-matched to the same agent,
  only enough combined headroom for one — assert the second falls through to its
  next-best capability candidate rather than both claiming the same tokens.
- `--execute` does not double-enqueue a story already `queued`/`running` in
  `daemon_jobs`.
- Degraded-mode fallback produces a plan (not empty/blocked) when `agent_quotas` is
  entirely unreadable.
- Dry-run (no `--execute`) never writes to `daemon_jobs`.
- Retry exclusion: a story with one `failed` `daemon_jobs` row for agent X is not
  reassigned to X while a capability-eligible alternative exists; is reassigned to X
  (flagged) when X is the only candidate.
- Retry cap: a story with `MAX_STORY_RETRIES` failed rows appears in
  `blocked: retry_exhausted`, not in the assignment table.
- Readiness gate: a `status='open', readiness='draft'` story never appears in a plan;
  `synlynk story ready` flips it into eligibility.

## Future work (explicitly out of scope for this design)

- **Reset-timing / bin-packing sequencing.** v1 assigns against a static headroom
  snapshot. A v2 could pack stories against each agent's `reset_at` so high-token
  stories front-load a window rather than leaving headroom stranded at reset — a
  genuine scheduling/interval problem, not a sort. Sequence after v1 has run long
  enough to show where the greedy version leaves value on the table.
- **Persistent quota-blocking history.** `blocked: quota` is computed per-run, not
  stored. If quota-blocking turns out to recur for the same stories across many
  scheduling passes, a `stories.block_reason` column with real invalidation logic
  would be the natural follow-up — deferred until there's a proven need for history
  over a point-in-time view.
- **Daemon-driven auto-scheduling.** Running `synlynk schedule --execute` on a timer
  instead of on-demand — deliberately excluded from this design to avoid new
  daemon-lifecycle infrastructure and surprise concurrent dispatches.
- **A more stringent, GOVERNS-aware readiness gate.** The v1 `readiness` flag is
  binary and single-story-scoped — it only answers "has someone looked at this," not
  "is the *plan* for this story holistic." A v2 gate should evaluate whether grooming
  reasoned through implications across each GOVERNS stage
  (`goal → open → visualize → execute → release → notify → sustain`, per
  `docs/superpowers/specs/2026-07-11-business-goal-sdlc-model-design.md`), not just
  the `execute` stage dispatch actually runs — e.g. a story ready to *build* but with
  no considered `release`/`notify`/`sustain` plan is exactly the "technically ready
  but not holistically planned" case that causes rework loops. Likely shape: a
  per-GOVERNS-stage checklist or required note before `readiness` can flip to
  `ready`. Depends on `chore/sdlc-goal-design` merging first — the capability-matrix
  hardening spec already notes `stories.stage` (the GOVERNS column) isn't live until
  that branch lands, and this gate would key off it.

## Acceptance

- `synlynk schedule` computes a plan across all ready, open, non-queued stories using
  existing #139 capability scores and #141 quota headroom, with the new fleet-level
  headroom accounting from step 6.
- `synlynk schedule --execute` writes assignments into `daemon_jobs` and triggers
  `_dispatch_ready_jobs()` without duplicating existing concurrency/dependency logic.
- `stories.readiness` gate exists; `draft` stories are never scheduled;
  `synlynk story ready`/`draft` commands manage the flag.
- Retry policy (exclude just-failed agent unless sole candidate; cap at
  `MAX_STORY_RETRIES`) is implemented and surfaced in plan output.
- Degraded quota data does not hard-block scheduling, consistent with #141 base's
  existing contract.
