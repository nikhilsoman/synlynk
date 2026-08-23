# Ticket-Driven Approval Auto-Resume — Design

## Goal

Make a resolved `[APPROVAL]` ticket actually unblock the story it parked. Today,
`synlynk tpm sweep` parks a policy-gated story by filing a GitHub ticket
(`raise_approval_ticket()`) and emitting `awaiting_approval`. When a human resolves
that ticket — closes it, or comments `approve` — `_scan_approval_tickets()` correctly
detects this and emits `approval_resolved` (confirmed live in the v0.16.0 dogfood,
event id 272). But nothing consumes that event. The next sweep pass re-evaluates
`check_authority()` from scratch, gets `requires_approval=True` again (the policy rule
still matches — policy doesn't know a human already said yes), and re-parks the story,
often re-filing a duplicate ticket in the process. This is exactly what produced the
stray `[APPROVAL]` issues #1130/#1131 during the dogfood run.

This closes the "natural next increment" gap named in the v0.16.0 CHANGELOG's Known
Gaps section, and is the next item on the informal full-autonomy roadmap toward
2026-08-31.

## Scope

**In scope:** a persisted story↔ticket link (`approval_tickets` table), using it both
to skip re-filing an already-open ticket and to let a resolved ticket unblock its
story on the next sweep pass. Both problems share the same missing piece of state, so
they land together.

**Out of scope:** changing `check_authority()`'s signature or making it ticket-aware —
it stays pure and policy-only. Wiring `scan_local_events()` to a dedicated cron
subcommand — it already runs incidentally via `_print_pending_nudges()` (called after
dispatch/status commands), and that cadence is sufficient for this increment.
Multi-workspace rollout (Phase 2/3) — not touched here.

**Explicitly not re-litigated:** the GOVERNS event contract, the approval-ticket
filing mechanism (`approval_gate.py`), and `check_authority()`'s policy-merge rules
are all shipped (v0.15.0/v0.16.0) and treated as given.

## Current mechanics (as read from code, not the prior spec's prose)

- `check_authority(action, role, repo_path)` → `AuthorityResult` — pure, re-reads
  `policy.json` every call, no caching, no ticket awareness.
- `raise_approval_ticket(story_id, action, reason, assignee, context)` — files a
  `[APPROVAL] <action> — <story_id>` GitHub issue via `gh issue create`, returns the
  issue URL (or `""` on failure). **Today this return value is discarded** —
  `run_sweep_pass()` never stores it.
- `_scan_approval_tickets()` (`synlynk/events.py`) — polls `gh issue list --search
  "[APPROVAL] in:title" --state all`, treats an issue as resolved if `state == CLOSED`
  or any comment starts with `approve`, and emits `approval_resolved` with payload
  `{"issue_url": ...}` for any not already recorded via `_existing_approval_resolved_keys()`.
  **The payload has no `story_id`** — there is currently no way to map a resolved
  ticket back to the story it was gating.
- `_ready_stories()` (`tpm_sweep.py`) filters `readiness='ready'` stories, excluding
  ones with a `daemon_jobs` row in `('queued','running','done')` (the last exclusion
  landed in PR #1135, closing #1133). This means once a story is genuinely dispatched,
  it naturally drops out of future sweep passes — the auto-resume problem is entirely
  about the gap *before* dispatch, not after.

## Data model

```sql
CREATE TABLE IF NOT EXISTS approval_tickets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id      TEXT NOT NULL,
    action        TEXT NOT NULL,
    issue_url     TEXT NOT NULL UNIQUE,
    status        TEXT NOT NULL DEFAULT 'open',  -- open | resolved | consumed
    opened_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at   TIMESTAMP,
    consumed_at   TIMESTAMP
);
```

`(story_id, action)` is not declared unique — a story could in principle be gated on
different actions over its life, or re-gated after a `consumed` ticket if policy still
requires approval on a later attempt. Lookups always filter by status, not assume
one row per story.

## Behavior changes

### 1. `run_sweep_pass()` — check tickets only as an override on `requires_approval`

`check_authority()` runs first, unchanged. Only when it returns
`requires_approval=True` does the sweep consult `approval_tickets`:

```python
if authority.requires_approval:
    ticket = _find_ticket(story_id, action, status="resolved")
    if ticket:
        _mark_consumed(ticket["id"])
        # fall through — proceed to dispatch below, same as authority.allowed
    else:
        existing_open = _find_ticket(story_id, action, status="open")
        if not existing_open:
            issue_url = raise_approval_ticket(story_id, action, authority.reason, assignee, context)
            if issue_url:
                _insert_ticket(story_id, action, issue_url)
            emit_awaiting_approval(story_id, action, authority.reason)
        summary["parked"] += 1
        continue

dispatch_agent(...)
summary["advanced"] += 1
```

A `consumed` ticket is never reused. If a later dispatch attempt for the same story
hits `requires_approval` again (e.g. a retry after failure, under an unchanged
policy), a fresh ticket is required — no stale approval carries forward silently.

### 2. `_scan_approval_tickets()` — write resolution back to `approval_tickets`

When it detects a resolved issue and emits `approval_resolved`, it now also updates
the linking table using the issue URL it already has as the join key — no title
parsing needed:

```python
conn.execute(
    "UPDATE approval_tickets SET status='resolved', resolved_at=? WHERE issue_url=? AND status='open'",
    (now, issue["url"]),
)
```

The `AND status='open'` guard makes this idempotent against re-scans of the same
resolved issue (on top of the existing `_existing_approval_resolved_keys()` de-dup for
the event itself).

## Error handling

- `raise_approval_ticket()` failing (`gh` error, network) — no row is inserted, same
  as today's discard behavior. Next pass retries filing. No new failure mode.
- Two sweep passes racing to file a ticket for the same story — out of scope; `tpm
  sweep` today runs as a single serial pass, not concurrently, matching existing
  assumptions elsewhere in `tpm_sweep.py`.
- A ticket resolved (closed/`approve`d) after its story was independently dispatched
  by some other path — the `resolved` row simply never gets consumed; harmless, no
  cleanup required.

## Testing

- `tpm_sweep.py`: unit tests for all three ticket-state branches — no ticket (files
  one), open ticket (skips re-filing, still parks), resolved ticket (consumes,
  proceeds to dispatch).
- `events.py`: `_scan_approval_tickets()` updates `approval_tickets.status` correctly
  on both resolution paths (issue closed, `approve` comment), and is a no-op on a
  second scan of the same resolved issue.
- Live dogfood: one pass reusing the `task_dispatch_demo`-style temporary policy rule
  from the v0.16.0 dogfood (Task 13's pattern) — park a demo story, resolve the
  ticket, run a second sweep pass, confirm the story dispatches instead of re-parking
  and no duplicate ticket appears.

## Exit criteria

- A story parked by `tpm sweep`, once its ticket is resolved, dispatches on the next
  sweep pass without manual intervention.
- Running `tpm sweep` twice against the same still-open ticket produces exactly one
  GitHub issue, not two.
- No change to `check_authority()`'s signature, tests, or call sites.
