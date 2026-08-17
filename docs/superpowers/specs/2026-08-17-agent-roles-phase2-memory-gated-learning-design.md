# Agent-Roles-Charters Phase 2 — Memory + Gated Learning — Design

**Date:** 2026-08-17
**Status:** Approved (pending final user sign-off on this written doc)
**Author:** Claude (pm), brainstormed with Nikhil Soman
**Parent:** `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` §10 (Phase 2: "durable memory keyed
to agent identity, wired into the *existing* capability ledger/SFIA/holdback design (§3.3, §7) rather than a new
store")

## 1. Motivation

Dispatches that name a `story_id` already get learned routing: `resolve_dispatch_harness()` (introduced in PR #1022)
tries `_best_agent_for_story()` first, which scores candidates from the `capability_scores` view — a recency-decayed
rollup of `capability_ratings`, written on every completed job that has a real story behind it. Only when that
returns `None` (no `story_id`, or genuine cold start) does it fall through to `_harness_for_org_role()`, a static,
alphabetical-first pick from `AGENT_CAPABILITY_BASELINES` that — per its own docstring — "does not consult the
story_id-based capability_scores DB table."

In practice, a large share of real dispatches are role/`agent_id`-driven (`--as-agent`, or an org role with no
`story_id` attached — ad hoc PM/architect/dev work not tracked against a roadmap story). Every one of those
dispatches permanently uses the static baseline: it never benefits from what's already been learned about which
harness performs best, and its own outcome is never recorded anywhere, so the gap never closes. This matches the
user's observed pain ("routing keeps picking the wrong harness") and was confirmed by direct code reading this
session: `_harness_for_org_role` is a pure, stateless lookup with no read or write path into `capability_ratings` /
`capability_scores` at all.

Phase 2 closes this gap using the *existing* learning substrate, per the parent roadmap's explicit instruction not
to build a new store.

## 2. Scope

**In scope:**
1. Story-less, role-driven dispatches read from `capability_scores` before falling back to the static baseline.
2. Story-less, role-driven dispatches write a `capability_ratings` row on completion, the same way story-based
   dispatches already do, so future role-driven dispatches benefit.
3. An explicit opt-out (`--static-baseline`) that skips the learned-routing read for a given dispatch and forces the
   raw `_harness_for_org_role` pick — for callers who want the deterministic baseline regardless of what's been
   learned (e.g. reproducing a known-good baseline, or diagnosing whether a routing regression is baseline-side or
   learning-side).

**Explicitly not in scope (per parent roadmap §10 and the Phase 1-followups spec §9):**
- `capability_grants` enforcement — Phase 3 (capability registry + scoped access grants), unscheduled.
- Any display/grouping UI for jobs-by-agent (`daemon_jobs.agent_id` consumption) — not phased at all; deferred as a
  separate future item if ever needed.
- A new agent_id-keyed memory table (Approach B, considered and rejected — see §3).
- Fine-grained per-discipline learning for role-driven dispatches — this phase treats role-driven capability signal
  as coarse, role-level-only (see §4). Discipline-aware learning stays exclusive to real, story_id-based dispatches.
- Issue #914 (workspace-level multi-repo agent identities) and issue #836 (Architect Workspace Agent as configurable
  context provider) — both open, unrelated to closing this specific routing gap; left as separate future work.

## 3. Approach

Three approaches were considered:

**Approach A (chosen): Extend the existing story_id-keyed pipeline via a synthetic per-org-role placeholder story.**
Give each of the 8 org roles (`dev`, `qa`, `architect`, `tpm`, `pm`, `designer`, `marketing`, `synlynk-bot`) a
deterministic, `INSERT OR IGNORE`-seeded row in `stories` (mirroring the existing `__baseline_seed__` pattern in
`capability_sweep.py`), and route story-less dispatches through the *same* `_best_agent_for_story` /
`_record_capability_rating` machinery real stories already use, keyed to that synthetic story. Zero changes to
`resolve_dispatch_harness()`'s control flow — it already tries story-based routing first and falls through to
`_harness_for_org_role` only on `None`; this approach only changes what `story_id` value reaches it.

**Approach B (rejected): New `agent_id`-keyed memory table**, parallel to `capability_ratings`, scored and merged
separately. Rejected because the parent roadmap explicitly says Phase 2 should wire into the *existing* ledger, not
create a new store — a second table would double the maintenance surface and require its own decay/scoring logic
that already exists for `capability_ratings`.

**Approach C (rejected): Minimal stopgap — no new learning, just make `_harness_for_org_role` prefer the
highest-baseline-score harness deterministically.** Rejected because it doesn't close the actual gap (role-driven
dispatches still never get scored on real outcomes) and doesn't use the calibration infrastructure already built for
this purpose.

## 4. Synthetic Role-Dispatch Story

One synthetic `stories` row per org role, seeded lazily (`INSERT OR IGNORE`, no eager migration):

- `story_id`: `f"__role_dispatch_{org_role}__"` — deterministic, pure function of `org_role`. No random component,
  no coordination needed between the read path (dispatch time) and the write path (completion time); both compute
  the same ID independently.
- `title`: `f"Role-dispatch capability signal ({org_role}) — synthetic, not a real story"` — mirrors the wording
  pattern of `__baseline_seed__`'s title, marking it clearly as non-real in any tooling that lists stories.
- `role`: `org_role` itself.
- `discipline`: `"general"` for all synthetic role-dispatch stories. This is a deliberate scope decision: role-driven
  dispatches get coarse, role-level-only capability learning in this phase, not fine-grained per-discipline
  learning. Discipline-aware scoring remains exclusive to real, story_id-based dispatches, which already carry a
  real discipline value from their actual story. Extending role-driven dispatches to a discipline-aware model is
  explicitly deferred (§2).
- `org_domain`, `industry`, `phase`: use the same schema defaults already in place for `stories` rows that don't
  specify them (unchanged from current behavior for any other minimal story insert).

**Critical isolation property:** the synthetic `story_id` is used **only** for the internal `capability_scores`
lookup and the `capability_ratings` write. It is never written to `daemon_jobs.story_id` or any other
job-persistence field. A role-driven dispatch's actual persisted state (job record, session linkage, cost
attribution, roadmap/TPM tracking) is completely unaffected — those systems continue to see `story_id: None` for
these jobs exactly as they do today. This avoids polluting any consumer of the real `story_id` field with a
synthetic placeholder value.

## 5. Read Path — `resolve_dispatch_harness()`

Today, `resolve_dispatch_harness(agent, agent_id, story_id, force_agent, requires_gh_write)` tries
`_best_agent_for_story(story_id)` when `story_id` is given, then falls through to `_harness_for_org_role` when that
returns `None` (including when `story_id` is `None`, i.e. every role-only dispatch today).

**Change:** when `resolve_dispatch_harness()` is called with `story_id=None` but a resolvable `org_role` (from
`agent_id` → `resolved_agent_role`, or from an explicit role argument), it computes the synthetic
`story_id = f"__role_dispatch_{org_role}__"` and calls `_best_agent_for_story(synthetic_story_id)` with that value —
using the exact same 3-stage scoring logic (capability score → quota headroom → cost tie-break) real stories already
get. If the synthetic story hasn't been seeded yet (true cold start for that role) or scoring still yields `None`,
the function falls through to `_harness_for_org_role` exactly as it does today — no behavior change for a role that
has never been dispatched before.

This function remains side-effect-free (no subprocess spawn, no DB write) — computing the synthetic ID and reading
`capability_scores`/`stories` is a pure lookup, so the existing `--dry-run` preview path continues to work
unchanged and shows the harness that would actually be picked, including for role-only dispatches.

**Opt-out flag:** `resolve_dispatch_harness()` gains a new `static_baseline: bool = False` parameter. When `True`,
the function skips the synthetic-story lookup entirely (for both real and role-driven dispatches) and goes straight
to `_harness_for_org_role`, ignoring `capability_scores` for the routing *decision* on this call. This is
implemented as a guard at the very top of the resolution logic — `if not static_baseline: try story-based routing`
— so it composes cleanly with the existing story_id-provided case too (a caller can force the static baseline even
when a real `story_id` was given).

Threaded through: a new `--static-baseline` CLI flag on `synlynk dispatch` (boolean, no argument — same shape as
`--force-agent`), plumbed to `dispatch_agent(..., static_baseline=False)` and from there into
`resolve_dispatch_harness()`. The dry-run preview branch in `cli.py` also passes it through, so
`--static-baseline --dry-run` previews the deterministic baseline pick.

**Opt-out does not suppress the write.** `static_baseline=True` affects only the read (routing decision) for that
one dispatch. The job's outcome is still recorded normally via the write path below — bypassing the learned pick for
one dispatch doesn't mean that dispatch's result stops being useful signal for future ones.

## 6. Write Path — `_record_capability_rating()`

Today, `_record_capability_rating(job)` (`synlynk/jobs.py`) looks up the job's story via
`SELECT ... FROM stories WHERE story_id = job['story_id']`; when `story_row` is `None` (true for every role-only
dispatch today, since `job['story_id']` is `None`), it returns immediately — no rating is ever written for these
jobs.

**Change:** when `job.get('story_id')` is falsy, `_record_capability_rating` derives the org role from the job's
`agent_id` (resolving through the same `agent_id` → `resolved_agent_role` path dispatch already uses) or from a
`role` field already present on the job record if `agent_id` isn't set. If a role can be resolved, it computes the
synthetic `story_id`, lazily seeds the synthetic `stories` row via `INSERT OR IGNORE` (mirroring
`_seed_capability_ledger_from_baseline`'s exact pattern — cheap, idempotent, no-op after the first job for that
role), and proceeds with the existing rating-computation and `INSERT INTO capability_ratings` logic unchanged,
using the synthetic story's `discipline`/`org_domain`/`role`/etc. as the joined values instead of a real story's.

If no role can be resolved at all (a genuinely anonymous dispatch with no `agent_id` and no `story_id`), the
function returns early exactly as it does today — this phase closes the role-driven gap specifically, not every
possible story-less dispatch shape.

## 7. Error Handling

No new user-facing failure modes. The synthetic-story seed is an `INSERT OR IGNORE`, so it cannot fail on races
between concurrent dispatches for the same role. If `agent_id` resolution fails (disabled/unregistered agent), the
existing `ValueError` from that resolution path is unchanged — this phase doesn't touch agent resolution itself,
only what happens after a role is successfully resolved. `--static-baseline` is a pure routing-decision flag with no
new validation surface (it doesn't conflict with `--force-agent`, `story_id`, or any other existing dispatch flag —
it only changes which internal lookup `resolve_dispatch_harness` performs).

## 8. Testing

- `resolve_dispatch_harness()`: role-only dispatch (no `story_id`) with an existing synthetic-story capability score
  picks the learned harness, not the static baseline.
- `resolve_dispatch_harness()`: role-only dispatch with no prior synthetic-story rating (cold start) falls through
  to `_harness_for_org_role`'s static pick, unchanged from current behavior.
- `resolve_dispatch_harness()`: `static_baseline=True` forces the static pick even when a synthetic-story score
  exists that would otherwise win.
- `resolve_dispatch_harness()`: `static_baseline=True` also forces the static pick when a real `story_id` with an
  existing score is given (opt-out applies uniformly, not just to role-driven dispatches).
- `_record_capability_rating()`: a completed role-only job (no `story_id`, has `agent_id`) writes a
  `capability_ratings` row keyed to the synthetic story, and the synthetic `stories` row is seeded on first write for
  that role.
- `_record_capability_rating()`: a second completed job for the same role does not re-insert the synthetic `stories`
  row (idempotent seed) and writes a second `capability_ratings` row as normal.
- `_record_capability_rating()`: a job with neither `story_id` nor a resolvable role still returns early with no
  rating written — unchanged existing behavior, confirmed not regressed.
- CLI: `synlynk dispatch --static-baseline` threads the flag through to `dispatch_agent()` and the `--dry-run`
  preview.
- Confirm `daemon_jobs.story_id` remains `None` for role-only dispatches after this change (isolation property from
  §4) — the synthetic ID must never leak into job persistence.

## 9. Out of Scope for This Spec

- `capability_grants` enforcement (Phase 3, unscheduled — parent spec §10)
- Display/grouping UI for `daemon_jobs.agent_id` (not phased)
- Approach B (separate `agent_id`-keyed memory table)
- Discipline-aware learning for role-driven dispatches (kept coarse/role-level-only, §4)
- Issue #914 (workspace-level multi-repo agent identities)
- Issue #836 (Architect Workspace Agent as configurable context provider)
