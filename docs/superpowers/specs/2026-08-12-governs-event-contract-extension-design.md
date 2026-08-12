# GOVERNS Event-Contract Extension — Design

**Date:** 2026-08-12
**Status:** Design; brainstormed and approved by Nikhil in chat 2026-08-12.
**Base document:** `docs/superpowers/specs/2026-08-11-autonomous-ops-program-design.md` — this spec fulfills that program's Week-1 (Autonomous Ops Lite, by 2026-08-16) v0.14.0 line item "GOVERNS event-contract extension."
**Related:** `synlynk/events.py` (the existing event bus this spec extends), `docs/superpowers/plans/2026-08-09-job-truth-and-gh-write-epics.md` (Epic A/B — the job-status-truthfulness and GH-write reliability work this spec makes event-observable).

---

## Objective

The existing GOVERNS event bus (`events` + `subscriptions` tables, `synlynk/events.py`, shipped via PR #817) wires up exactly 4 event types today: `pr_merged`, `story_done`, `spec_or_plan_committed`, `cron_heartbeat`. None of them cover job dispatch outcomes or PR review activity — the two things this week's release gates actually need to observe:

- "100% of terminal jobs have cost data or explicit `cost_missing` status" (from `docs/strategy/road-to-autonomous-ops.md`'s release gates)
- "No unreviewed autonomous merge"

Today, verifying either gate means manually running `synlynk jobs`/`synlynk ops report` or reading `state.db` directly. This spec adds two new event types so both become event-observable, plus a CLI surface to read them — giving this week's manual autopilot-lite loop run (program-design spec item 3) and its friction measurement (item 5) something concrete to watch. (The `job_terminal` event surfaces whether a cost row was recorded at the moment a job settles; it does not itself compute the gate's "100%" aggregate — that still comes from the existing `cost_entries`/A2 mechanism, unchanged by this spec.)

**Explicitly out of scope this week** (deferred to the base strategy doc's Week 3, 08-31→09-13): `issue_opened`/`issue_closed` event types, GitHub Issue mirror fields, `external_untriaged` disposition. This spec touches none of that.

## Two new event types

### 1. `job_terminal`

**Emission point:** synchronous, in-line, inside `_reconcile_daemon_jobs()` (`synlynk/jobs.py:2045`) — the existing GTV (Ground-Truth Verification) reconcile loop that already determines a job's true terminal status and calls `_ensure_daemon_job_cost_entry()` (currently called at lines 2125, 2217, 2221). This is a real code hook already on the daemon's poll-tick path — no new scan step, no polling delay.

An event is emitted once per job the moment `_reconcile_daemon_jobs()` settles it into a terminal state (`done`, `failed_unverified`, or any other GTV-verified terminal status), immediately after the existing `_ensure_daemon_job_cost_entry()` call at that site, using that call's own return value.

**Payload:**
```json
{
  "job_id": "job-bb7f1db7",
  "status": "done",
  "cost_recorded": true,
  "dispatch_context": "headless"
}
```
`_ensure_daemon_job_cost_entry()` returns `True` only when it wrote a *new* cost row — it returns `False` both when a row already existed (nothing missing) and when it couldn't write one (genuinely missing). Since the two `False` cases are indistinguishable from the return value alone, `job_terminal` reports `cost_recorded` as-returned rather than inventing a `cost_missing` flag the underlying function can't actually support; a consumer that needs to distinguish "already had a cost row" from "still missing one" queries `cost_entries` by `job_id` directly (existing A2 mechanism, unchanged) rather than relying on this event's payload alone.

**Idempotency:** `_reconcile_daemon_jobs()` may observe the same job across multiple poll ticks before it's fully settled, but it only calls `_ensure_daemon_job_cost_entry()` once terminal state is confirmed and does not re-process already-terminal jobs on subsequent ticks (existing behavior, unchanged). The `job_terminal` event emission is added at the same call site, so it inherits the same at-most-once guarantee — no separate dedup logic needed.

### 2. `review_submitted`

**Emission point:** cannot be synchronous. `gh pr review` is invoked as a raw shell command directly by dispatched agents (confirmed: no synlynk command wraps PR review submission — `synlynk pr check` only runs pre-merge checks, per `synlynk/db.py:2381`). This has to be scan-detected, following the exact pattern `scan_local_events()` already uses for `pr_merged` (`synlynk/events.py:76-99`, which polls `gh pr list --state merged`).

Extend `scan_local_events()` with a third scan block: for merged PRs found in the existing `pr_merged` scan (already fetched via `gh pr list --state merged --limit 20 --json number,title,mergedAt`), additionally call `gh pr view <number> --json reviews` and check for any review rows not already represented by a `review_submitted` event (dedup by `(pr_number, reviewer_login, submitted_at)` — checked against existing event payloads for that PR, since reviews don't have a monotonic id usable as a checkpoint the way merged-PR-list does). Emit one `review_submitted` event per new review found.

**Payload:**
```json
{
  "pr_number": 919,
  "reviewer_login": "synlynk-vdowrx-qa[bot]",
  "reviewer_role": "qa",
  "verdict": "COMMENTED"
}
```
`reviewer_role` is derived from `reviewer_login` by matching against the known per-repo GitHub App slug pattern (`synlynk-<repo-slug>-<role>[bot]`, e.g. `synlynk-vdowrx-qa[bot]` → `qa`) established by the identity-provisioning work (program-design spec, modification 1). If `reviewer_login` doesn't match that pattern (a human reviewer, or a repo without role identities provisioned yet), `reviewer_role` is `null`.

**Scope limitation, stated explicitly:** this scan only looks at the last 20 merged PRs (same window `scan_local_events()` already uses for `pr_merged`) — reviews on PRs outside that window, or on PRs still open, are not scanned. This is consistent with the existing `pr_merged` event's scope and is not a new limitation introduced by this spec. Widening the scan window is out of scope here.

## New CLI surface: `synlynk events tail`

```
synlynk events tail [--type TYPE] [--limit N]
```

- Reads directly from the existing `events` table (no new table). Newest-first.
- `--type` filters to one event type (any of the now-6 wired types); omitted shows all types interleaved.
- `--limit` defaults to 20.
- Output format: one line per event — `<id>  <created_at>  <event_type>  <emitted_by>  <compact payload summary>`.

This is a read-only diagnostic command, not a new consumer/subscriber — it does not touch `subscriptions` or advance any checkpoint. It exists so this week's manual autopilot-lite loop run and friction measurement (program-design spec items 3 and 5) have something to look at without querying `state.db` directly via `sqlite3`.

## Data flow summary

```
_reconcile_daemon_jobs()  ──emit_event("job_terminal", ...)──▶  events table
scan_local_events()       ──emit_event("review_submitted", ...)──▶  events table
                                                                        │
                                                          synlynk events tail  (read-only)
```

No changes to `subscriptions`, `advance_checkpoint()`, or the existing pilot `workspace_agent.py` consumer — it is not extended to subscribe to the two new types in this spec (that remains Week 2's TPM/session MVP work, per the base program-design spec).

## Testing

- **`job_terminal` emission:** unit test that fakes a job reaching terminal state through `_reconcile_daemon_jobs()` and asserts a `job_terminal` event row is written with the correct `status` and `cost_recorded` value in both the new-row-written and row-already-existed cases (mirrors existing GTV tests' fake-dead-PID fixture pattern).
- **`review_submitted` emission:** unit test that mocks the `gh pr view --json reviews` subprocess call inside `scan_local_events()` and asserts one `review_submitted` event is emitted per new review, with `reviewer_role` correctly derived from a `[bot]` login and correctly `null` for a non-matching login. A second test asserts no duplicate event is emitted on a second scan when no new reviews exist.
- **`synlynk events tail`:** test asserting `--type` filtering and `--limit` truncate/order correctly against a seeded `events` table.

## Decision

Add `job_terminal` (synchronous, from the existing GTV reconcile hook) and `review_submitted` (scan-detected, extending the existing `pr_merged` scan pattern) as two new GOVERNS event types, plus a read-only `synlynk events tail` CLI command to observe all 6 wired event types. No schema changes — both event types use the existing `events` table and `payload_json`'s free-form shape. No new consumer/subscriber is added this week; that is Week 2 scope.
