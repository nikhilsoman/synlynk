# Quota-Aware Dispatch Reservation — Design

**Status:** Draft, pending user sign-off
**Parent context:** fleet-autonomy foundation (workspace-agent-fleet vision), second sub-project after Agent Charters was deferred to brainstorm second
**Related:** `synlynk/quota.py` (#141, existing), `synlynk/scheduler.py` (existing), issue #291 (existing quota-refresh wiring), issue #426/#569 (GitHub write routing — separate, referenced only for context)

## Naming Collision — Read This First

Following the precedent in `docs/superpowers/plans/2026-07-24-agent-github-identity-design.md`'s "Naming Collision" section, this design adds a fourth meaning to a word that already has too many:

1. **Permission-scope roles** (existing) — `.synlynk/config.json`'s `"roles"` key maps *agent* → permission-scope strings. Untouched by this design.
2. **Capability-taxonomy roles** (existing) — `stories.role` / `_ROLES` enum: `architect`, `dev`, `pm`, `tpm`, `qa`, `designer`. The future "TPM workspace agent" the user described is this `role='tpm'` dimension — not a new concept.
3. **`.synlynk/roles.yaml` identity roles** (existing, from the identity design).
4. **`agent` = core harness binary** (existing usage throughout `quota.py`, `dispatch.py`, `AGENT_CAPABILITY_BASELINES`, `_KNOWN_AGENT_BINARIES`): `claude` / `agy` / `codex` / `grok` / `local`. This is the dimension that actually has a rate-limit window and is what this design's reservation ledger tracks.

**Rule for this design and all new code it introduces:** never let a `role` value (`tpm`, `pm`, `dev`, ...) flow into a column or parameter typed for harness identity, and vice versa. Every new function signature in this doc uses `harness: str` and `role: str` as distinct, never-interchangeable parameters.

**Canonical vocabulary going forward:** user-facing text (CLI help, README, CLAUDE.md, error/print strings) should say **"harness"**, not "agent," when referring to `claude`/`agy`/`codex`/`grok`/`local`. `agent` remains the internal Python/DB identifier for now — renaming the ~2,073 internal occurrences and 5 DB columns is out of scope for this design and tracked separately as [issue #786](https://github.com/nikhilsoman/synlynk/issues/786). This design's *new* table introduces the `harness` column name so new code doesn't inherit the debt it just identified, but does not rename the existing `agent_quotas`/`daemon_jobs`/`cost_entries` columns.

## Problem

`synlynk/quota.py` (679 lines) already implements per-harness quota tracking: `QUOTA_TYPES = ("5h", "hourly", "daily", "weekly", "monthly")`, telemetry-derived usage aggregation, and a working `synlynk quota` status command. Quota is even consulted at routing time via `_best_agent_for_story()` (`synlynk/jobs.py:1020`), which is called from `dispatch_agent()` — but **only when `story_id` is set and `force_agent` is `False`** (`synlynk/dispatch.py:1656`: `if story_id and not force_agent`).

This means the most common real dispatch pattern — `synlynk dispatch <agent> --task "..." --force-agent --context-mode full`, which is CLAUDE.md's own documented standard invocation — bypasses quota checking entirely. Ad-hoc dispatches with no `story_id` bypass it too.

A second, independent bug compounds this: `_dispatch_ready_jobs()` (`synlynk/jobs.py:2034`) re-runs `_best_agent_for_story()` for already-queued jobs to *reroute* to a harness with headroom. If every capability-eligible harness is quota-exhausted, `_best_agent_for_story()` returns `None`, and the code falls through to dispatching the **original, exhausted harness anyway** — deferral doesn't actually happen today.

`scheduler.py`'s batch path (`synlynk schedule`) has its own separate, in-memory-only headroom accounting (`_compute_schedule_plan()`'s `headroom_cache`), explicitly dry-run by the module's own docstring — nothing is persisted when a batch plan is committed via `_enqueue_plan()` until each job individually fires later.

Net effect: quota tracking exists and is fairly sophisticated, but there is no single, consistently-enforced reservation of budget across (a) a single dispatch, (b) a plan's sequence of tasks, or (c) a session/day's full dispatch queue — and the one enforcement path that does exist has a silent bypass and a silent fall-through bug.

## Goals

1. One shared reservation ledger, consulted from every dispatch path (`--force-agent`, ad-hoc, queued/daemon, batch-scheduled) — not three divergent headroom calculations.
2. Fix the `--force-agent`/no-`story_id` bypass and the all-exhausted fall-through bug as part of wiring the ledger in, not as separate patches.
3. Auto-defer (queue-and-wait), never hard-fail, when headroom is insufficient — matching the existing "hit 5h, wait, resume, nothing lost" workflow already used manually today.
4. Leave clean, narrow hook points for a future `role='tpm'` workspace agent to observe/reorder/reallocate the ledger, without building that agent now.
5. Document, not solve, the real limitation that harness plan limits and cross-surface usage are not observable from CLI output — and add a reactive-correction path for the one signal that is observable (an actual rejection during a dispatch).

## Non-Goals

- The full `agent` → `harness` internal/DB rename (2,073 occurrences, 5 DB columns) — tracked as [issue #786](https://github.com/nikhilsoman/synlynk/issues/786).
- Building the actual `role='tpm'` workspace agent — only its hook surface.
- Discovering real plan-type limits or cross-surface (IDE, web) usage automatically — no such API exists today.
- Fixing `update_costs()`'s hardcoded per-token $ rates — separate, unrelated concern, tracked as [issue #787](https://github.com/nikhilsoman/synlynk/issues/787).
- Agent Charters (the sibling fleet-autonomy sub-project) — deferred to its own brainstorm.

## Data Model

```sql
CREATE TABLE agent_reservations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    harness        TEXT NOT NULL,        -- 'claude'|'agy'|'codex'|'grok'|'local'
    tokens         INTEGER NOT NULL,
    scope          TEXT NOT NULL,        -- 'plan' | 'session' | 'adhoc'
    scope_id       TEXT,                 -- plan file slug or session id; NULL for adhoc
    job_id         TEXT,                 -- daemon_jobs.job_id once the dispatch actually fires
    status         TEXT NOT NULL DEFAULT 'open',  -- 'open' | 'released' | 'expired'
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    released_at    TIMESTAMP
)
```

- Table name stays `agent_reservations` (not `harness_reservations`) — nothing else references the table name yet, so there's no rename cost to avoid; only the `harness` column mattered for the ambiguity this design is closing.
- **Reserve on intent, release on settlement.** A reservation opens the moment tokens are committed against a harness (plan projection at `_enqueue_plan()` time, or `dispatch_agent()` about to fire) and is released once real telemetry for that dispatch lands in `daemon_jobs`/`cost_entries` (the existing `_refresh_agent_quotas_from_telemetry()` reconciliation path) — at that point the reservation's estimate is superseded by real usage and would double-count if left open.
- **Lazy expiry**, not a cron: reservations older than 24h are treated as `expired` when read (not physically deleted), so an abandoned plan doesn't permanently lock capacity. 24h is chosen as comfortably longer than any single quota window (`5h` is the shortest) so a legitimately-still-running plan is never prematurely expired.
- `_quota_status_for_agent()`'s headroom computation changes from `limit - used_tokens` (telemetry only) to `limit - used_tokens - open_reservations_sum` (open, non-expired reservations for that harness/window included).

## Dispatch-Time Flow

`dispatch_agent()` (`synlynk/dispatch.py:1635`) changes:

1. **Before spawning the subprocess**, unconditionally (no longer gated on `story_id and not force_agent`) compute `estimated_tokens` — reuse the existing story `estimated_tokens` column when a `story_id` is present, fall back to a task-string-length heuristic for ad-hoc calls with none — and call `_quota_status_for_agent(conn, agent, estimated_tokens=...)`.
   - `force_agent=True` continues to mean "don't let routing pick a *different* harness than the one named" — it does **not** mean "skip the budget check on the harness that was picked." These are separable concerns and conflating them was the original bug.
2. **If headroom exists:** open an `agent_reservations` row (`status='open'`, `scope` inferred from context — `'plan'` if called from a plan-driven dispatch, `'session'` otherwise, `'adhoc'` if neither), proceed to dispatch as today.
3. **If headroom is insufficient:** do not raise. Insert/update the `daemon_jobs` row as `status='queued'` with a new `blocked_reason='quota_exhausted'` column, and return `{"deferred": True, "reason": ..., "retry_after": <agent_quotas.reset_at ISO timestamp>}` instead of a live job handle.
4. **`_dispatch_ready_jobs()` fall-through fix:** when `_best_agent_for_story()` (or the equivalent unconditional check for non-story jobs) finds every candidate harness exhausted, the job **stays `queued`** — it must not fall through to dispatching an exhausted harness. This is the concrete fix for the bug found during this design's research.
5. **On settlement** (existing `jobs.py` reconciliation path, when a job reaches `done`/`failed`): release the matching `agent_reservations` row (`status='released'`, `released_at` set). Real telemetry has landed by this point via the existing `_refresh_agent_quotas_from_telemetry()` call, so the reservation is redundant, not additive.

### Wait/resume policy (no hard-fail, no killed work)

- Reactive quota-exhaustion detection (see below) never touches `running` jobs — in-flight context and output are not discarded.
- New dispatch attempts to an exhausted harness are deferred (step 3 above), not rejected.
- Already-`queued` jobs for that harness are left in place. `agent_quotas.reset_at` already tracks the window boundary; the existing `synlynk watch` daemon poll loop (`daemon.py`, confirmed calling `_dispatch_ready_jobs()` on every tick) picks deferred jobs back up automatically once `reset_at` passes and headroom reopens — no explicit `synlynk resume` command is needed. This reproduces, without user action, the "hit 5h, wait, say resume, nothing lost" behavior already relied on manually today.

## `scheduler.py` Changes

- `_compute_schedule_plan()`'s in-memory `headroom_cache` (lines 94-113) is unchanged in structure — it remains an explicit dry-run preview. It automatically becomes reservation-aware for free, since it already calls `_quota_status_for_agent()`, which now subtracts open reservations as part of its headroom math.
- `_enqueue_plan()` (lines 156-192) gets a real gap closed: today it only inserts `daemon_jobs` rows, so a committed batch plan isn't reflected in the quota system until each job individually fires later through `dispatch_agent()`. This design adds: for each item in the plan, open an `agent_reservations` row (`scope='plan'`, `scope_id=<schedule-run-id>`, `harness=item["agent"]`, `tokens=item["estimated_tokens"]`) at the same time the `daemon_jobs` row is inserted — so committing a batch schedule is immediately visible in the reservation ledger, not just eventually.

## Reactive Correction (the one observable ground-truth signal)

**What's not observable:** no harness CLI exposes plan-type or true remaining ceiling via stdout/JSONL. `_DEFAULT_QUOTA_LIMITS` (and its `.synlynk/config.json` override) are operator-declared assumptions, not observed facts — if the configured tier doesn't match the actual plan, headroom math is silently wrong until manually corrected. Usage from other surfaces sharing the same plan (an interactive terminal session outside synlynk, an IDE extension) is invisible to synlynk's telemetry — `used_tokens` only reflects what synlynk itself dispatched and captured. Dynamic vendor-side limit changes (temporary relaxation/hardening) are not proactively knowable either. This design does not solve any of these — no polling API exists — but states them explicitly so the reservation ledger is never presented as more authoritative than it is: it is **synlynk-observed headroom**, a floor on risk, not a guarantee.

**The one real signal:** `sentinel.py` already string-matches quota-exhaustion phrases in captured harness output (`QUOTA_PATTERNS`, `sentinel.py:477-486`) and writes a `QUOTA_EXHAUSTED` alert to `sentinel.md` — but today that detection is a dead end; it never corrects `agent_quotas`. This design wires it up: on a `QUOTA_EXHAUSTED` match, in addition to today's alert write, call a new `_force_exhaust_quota(conn, harness, window)` in `quota.py` that zeroes that harness's headroom for the current window immediately. This is the one moment synlynk gets real ground truth (an actual rejection), so it's treated as authoritative, overriding whatever the blind proactive estimate said. Per the wait/resume policy above, this only blocks *new* dispatches and leaves running/queued jobs to resume naturally once `reset_at` passes.

## TPM Hook Stubs

Three narrow, independently-testable pure functions in a new `synlynk/tpm_hooks.py` — not a TPM agent implementation, but the stable surface a future `role='tpm'` dispatch calls instead of touching tables directly. Each takes `harness`/`role`-typed parameters per the naming rule above, never conflating the two:

```python
def tpm_observe_reservations(conn, scope: str = None, scope_id: str = None) -> list[dict]:
    """Read-only: open reservations + live headroom per harness, optionally
    filtered to one plan/session scope. Backs `synlynk quota tpm-view`."""

def tpm_reorder_queue(conn, priorities: dict[str, int]) -> int:
    """Bulk-update daemon_jobs.priority for {job_id: new_priority}. Returns rows
    changed. Pure reprioritization -- does not touch reservations or harnesses."""

def tpm_reallocate(conn, job_id: str, new_harness: str) -> dict:
    """Move a queued (not yet running) job's reservation from its current harness
    to new_harness: release old reservation, open new one, update daemon_jobs.agent.
    Raises if job_id is not status='queued' (can't reallocate a running/done job)."""
```

`tpm_observe_reservations` ships with one real caller in this PR — a read-only `synlynk quota tpm-view` CLI wrapper — so nothing lands as dead code. `tpm_reorder_queue` and `tpm_reallocate` ship covered by direct unit tests against real tables; no mock TPM caller exists yet since the workspace agent itself is out of scope here.

## Deferred Follow-Ups

1. **Internal `agent` → `harness` rename** — [issue #786](https://github.com/nikhilsoman/synlynk/issues/786). CLI flags, ~2,073 internal occurrences across 34 files, 5 DB columns (`daemon_jobs.agent`, `agent_quotas.agent`, `cost_entries.agent`, etc.), README/CLAUDE.md prose. User-facing text switches to "harness" as part of this design; the internal rename is separate, larger, and not blocking.
2. **Cost-estimation accuracy vs. real billing** — [issue #787](https://github.com/nikhilsoman/synlynk/issues/787). `update_costs()`'s hardcoded `$0.003/1K in + $0.015/1K out` doesn't account for flat-rate subscription plans where marginal $ cost may be $0, or metered-plan pricing differences. Separate concern from whether headroom exists.
3. **Plan-limit calibration** — no `synlynk quota calibrate` or equivalent exists to let a user declare their actual plan tier interactively; today it requires hand-editing `.synlynk/config.json`. Worth a small follow-up once the reservation ledger is live and the calibration gap becomes a felt friction rather than a theoretical one. Not yet filed as an issue — small enough to fold into the implementation plan directly if it turns out to be needed for testing calibration realistically.

## Testing Approach

- **Unit, no live harness calls:** `agent_reservations` open/release/expire lifecycle; `_quota_status_for_agent()`'s headroom math with open reservations subtracted; `_dispatch_ready_jobs()`'s fixed fall-through (all-exhausted → stays queued); `_force_exhaust_quota()` zeroing without touching `running` rows; `tpm_reallocate()`'s queued-only guard; `tpm_reorder_queue()`'s bulk update.
- **Integration:** a fake multi-task plan against a tmp sqlite db exercising the full reserve → dispatch → settle → release cycle across 2+ harnesses; an exhaustion scenario proving a deferred job survives a `reset_at` boundary and is picked up by a second `_dispatch_ready_jobs()` call without re-dispatching already-`done` jobs.
- **Regression:** full existing suite (currently 1730 passed / 2 skipped) must stay green — this design touches `dispatch_agent()`, `_dispatch_ready_jobs()`, `_quota_status_for_agent()`, and `scheduler.py`, all of which have existing callers and tests.
