# GOVERNS Backlog Automation — Design

Part of #1198 (Element 2). Closes the design gate on #1203.

## Problem

No mechanism exists to automatically add newly discovered work, planned future work, or
work surfaced during interactive harness sessions to the backlog with correct GOVERNS
association. Filing today is entirely manual (`gh issue create --parent ...`), so
discovered work either gets filed inconsistently by whoever remembers, or is lost when a
session closes without anyone writing it down as a ticket.

## Prior art this design builds on

`synlynk/support_engineer.py` already implements the shape this problem needs, for a
different signal source: `cmd_agent_run` collects signals (`_collect_test_suite`,
`_collect_sentinel_alerts`, ...) → `_dedup_findings` (hash-based) → `_run_investigation`
→ `_file_gh_issue` → records the result in `autopilot_runs` (`gh_issue_url`, `story_id`,
`status`, `signal_hash`). Separately, `synlynk/db.py`'s `approval_tickets` table already
cross-references a `story_id` to an `issue_url` for a different flow
(`raise_approval_ticket` / `_insert_ticket` in `tpm_sweep.py`).

This design reuses that pattern — a new collector and archetype feeding the existing
autopilot pipeline — rather than building a parallel filing/dedup/ledger system.

## Entry paths

Two paths feed one pipeline. Only the collection/triggering differs; dedup, filing, and
GOVERNS association are shared.

### 1. Explicit marker (primary path)

`synlynk backlog note "<title>" [--body ...]` — called live, in-session, by an agent
(in practice Claude, since backlog filing is PM-role work per this repo's role split)
when it notices discovered or planned work worth tracking.

Calling the command *is* the deliberate human-directed act — it runs dedup (below) and
files immediately on a dedup miss. No separate confirm step. This bypasses
`cmd_agent_run` entirely (it's synchronous and user/agent-invoked, not a scheduled
collector sweep) and calls the shared dedup/file helpers directly.

### 2. Session-close safety net

A new collector, `_collect_session_discoveries`, added to the `collector_map` in
`cmd_agent_run`, under a new archetype `backlog_scribe`
(`collectors: [session_discoveries]`, `fixer: none` — this archetype only files, it
never attempts fixes the way the existing autopilot flow's `_attempt_fix` does).

At session close (the existing `sessions` table close/disposition step), Claude reads
the closing `sessions.closing_summary` and the devlog delta written for that session,
and classifies candidate items as file-worthy or not — the same judgment call already
made when deciding devlog vs. memory content, not a rigid keyword/pattern list.
Candidates that pass dedup are presented as a short yes/no list; nothing is filed until
confirmed. This is a safety net for work that should have gone through the marker path
but wasn't flagged live — it is deliberately lower-trust (confirm-gated) than the marker
path (immediate-file), matching the project's existing `requires_approval`/
`awaiting_approval` gating philosophy in `events.py` for anything a scheduled sweep,
rather than a live human-directed call, is about to write to GitHub.

## Dedup

Two layers — they catch different failure modes:

- **`gh search_issues`**: before filing, search open/closed issue titles/keywords for a
  match. Catches duplicates against real filed work.
- **Local ledger, `backlog_proposals`** (sibling to `autopilot_runs`):

  ```sql
  CREATE TABLE IF NOT EXISTS backlog_proposals (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      signal_hash     TEXT NOT NULL,
      title           TEXT NOT NULL,
      source          TEXT NOT NULL,   -- 'marker' | 'session_close'
      status          TEXT NOT NULL,   -- 'filed' | 'declined'
      gh_issue_url    TEXT,
      story_id        TEXT,
      goal_id         TEXT,
      goal_match_basis TEXT,
      session_id      TEXT,
      ts              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```

  `signal_hash` is a hash of the normalized title + source. A candidate whose
  `signal_hash` already has a `backlog_proposals` row (filed *or* declined) is skipped
  before it ever reaches `gh search_issues` — this is what catches repeat-proposal noise
  from a declined candidate that never became a GitHub issue and so has nothing for
  `gh search_issues` to match against.

## Filing / GOVERNS association

On file: create the GitHub issue (`--parent <active tracking issue>` plus appropriate
labels — matching how #1199 and #1203 themselves were filed under #1198) **and** a
`stories` row (`story_id`, `title`, `stage='open'`, `readiness='draft'`), linked via
`goal_contributions` to a `goals` row. The `backlog_proposals` row stores `gh_issue_url`,
`story_id`, and `goal_id` together so the ledger, the GitHub issue, and the local story
are all traceable to each other and to the originating session.

### Goal association when `sessions.goal_id` is unset

Not every session works against an explicit goal. When `sessions.goal_id` is set, use
it directly. When it isn't:

1. Claude reasons over open `goals` rows' `outcome`/`criterion` text and picks the
   closest match, if one is a good fit.
2. If no existing goal is a good match, Claude creates a new `goals` row (`outcome`,
   `criterion` derived from the story's context, `status='active'`) and links the story
   to that instead.

Both cases are **silent** — no added confirm step, consistent with the marker path's
"the call itself is the deliberate act" trust level and with keeping the session-close
safety net's confirm gate scoped to *whether to file at all*, not to every downstream
detail of how it gets filed. Every guess (existing-goal match or new-goal creation) is
fully audited: `backlog_proposals.goal_match_basis` records the reasoning (why this goal
matched, or why none did and what the new goal's outcome/criterion are), so a wrong
guess is traceable and correctable after the fact rather than silently invisible.

## Non-goals

- Not touching `support_engineer.py`'s existing `test_suite`/`sentinel_alerts`
  collectors or the `_attempt_fix` flow — `backlog_scribe` is filing-only.
- Not building a UI for reviewing `backlog_proposals` — `gh issue list --label ...` and
  direct SQL against the ledger are sufficient for now; a dashboard view is a future
  enhancement if the volume warrants it.
- Not retroactively backfilling `backlog_proposals` for work discovered before this
  ships (e.g. #1264 vs #1263 dedup, flagged in #1199's wrap-up) — this system governs
  new discoveries going forward.

## Open items for the implementation plan

- Exact title-similarity threshold for the `gh search_issues` dedup check (needs a
  concrete value/algorithm, not just "similar").
- Where `backlog_scribe`'s archetype config lives relative to existing archetypes in
  `_load_agent_config` — follow existing config file conventions exactly.
- Whether `synlynk backlog note` needs a `--dry-run` flag mirroring `cmd_agent_run`'s
  existing `dry_run` parameter, for consistency with the rest of the CLI surface.
