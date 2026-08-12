---
title: "chore/governs-event-contract-extension — Two New Event Types for the Autonomous Ops Release Gates"
date: 2026-08-13
series: "Building the OS for Multi-Agent Development"
post: 115
pr: "TBD"
---

# 115: Two New Event Types for the Autonomous Ops Release Gates

## Broader goal (previous)

By the landing of the Road to Autonomous Operations strategy and its program-design spec (PR #915, 2026-08-12), the Autonomous Ops Lite milestone (target 2026-08-16) had two of its five Week-1 items done — cc-videoreframing's 8-role identity provisioning, and the roadmap-governance strategy resolution. Three remained: choosing a real synlynk goal and running the autopilot-lite loop manually, shipping v0.14.0, and measuring attribution friction from that loop run. The program-design spec named two concrete release gates the October 1 preview depends on: "100% of terminal jobs have cost data or explicit `cost_missing` status" and "no unreviewed autonomous merge." Verifying either meant hand-querying `state.db` — there was no event-observable surface for job settlement outcomes or PR review activity.

## Why this PR

The GOVERNS event bus (`synlynk/events.py`, shipped via PR #817) already wired 4 event types — `pr_merged`, `story_done`, `spec_or_plan_committed`, `cron_heartbeat` — but none of them touched job dispatch outcomes or review submissions, the two things the release gates actually need to watch. This chore closes that gap with a small, deliberately scoped design: two new event types plus a read-only CLI to inspect them, built on the existing `events` table with zero schema changes.

`job_terminal` had to be synchronous — `_reconcile_daemon_jobs()` (the GTV reconcile loop) already determines a job's true terminal status and calls `_ensure_daemon_job_cost_entry()` at two settlement paths, so the event rides that existing hook rather than introducing a new poll. `review_submitted` couldn't be — `gh pr review` is a raw shell command invoked directly by dispatched agents, with no synlynk wrapper to hook into — so it had to be scan-detected, extending the existing `pr_merged` scan pattern in `scan_local_events()` with a `gh pr view --json reviews` call per merged PR, deduplicated by `(reviewer_login, submitted_at)` since reviews have no monotonic checkpoint the way the merged-PR list does.

One correction surfaced between design and plan: the approved spec's stated dedup key referenced `submitted_at`, a field its own payload example omitted. Rather than reopening the already-approved spec, the plan added `submitted_at` to the payload with an explicit rationale note — the dedup key needed a field that existed to compute against.

## What shipped

Execution followed brainstorming → writing-plans → subagent-driven-development, with all three tasks dispatched to Codex (`synlynk dispatch codex`) per this repo's Claude=PM/review-only role split, one at a time in strict order since Tasks 2 and 3 both touch `synlynk/events.py`.

- **`synlynk/jobs.py`** — `_reconcile_daemon_jobs()`'s `SELECT` and row-unpacking now carry `dispatch_context`; both settlement paths (`preferred-summary` and `guaranteed`) capture `_ensure_daemon_job_cost_entry()`'s own return value as `cost_recorded` and emit `job_terminal` with `{job_id, status, cost_recorded, dispatch_context}` immediately after. The `except`-block's defensive cost-entry call was deliberately left unmodified — the guaranteed call always re-runs right after it, so emitting there too would double-fire the event.
- **`synlynk/events.py`** — three new helpers: `_reviewer_role_from_login()` (regex-matches the `synlynk-<repo-slug>-<role>[bot]` GitHub App login pattern, `None` for non-matching logins), `_existing_review_submitted_keys()` (payload-content dedup query, since reviews have no id-based checkpoint), and `_scan_pr_reviews()` (the `gh pr view --json reviews` call plus emission), wired into the existing `pr_merged` loop in `scan_local_events()`.
- **`synlynk events tail [--type TYPE] [--limit N]`** — new read-only CLI command, `cmd_events_tail()` in `events.py` plus a subparser/dispatch block in `cli.py` mirroring the existing `identity` command exactly. Since `synlynk.events` isn't re-exported through `synlynk/__init__.py` (unlike most other command modules), the CLI wiring uses a direct `from synlynk.events import cmd_events_tail` import rather than the giant re-export block.
- **Tests** — 7 new tests across `tests/test_jobs.py` (3, covering both `cost_recorded` branches plus the preferred-summary path) and `tests/test_events.py` (6, covering role derivation, `None` for non-matching logins, no-duplicate-on-rescan, and `--type`/`--limit` filtering), plus one existing test (`test_scan_local_events_emits_pr_merged_from_gh_output`) updated from a single shared `mock_run.return_value` to a `side_effect` list, since the new `gh pr view` call per merged PR broke the old single-mock assumption.

Task 3's implementer also caught a real regression the plan hadn't anticipated: registering `events tail` in `synlynk/taxonomy.py`'s `COMMAND_TAXONOMY` (required — every leaf CLI command needs an entry) left `docs/reference/commands.md` stale against its own generator-parity test. That got fixed as a small follow-up commit, running the existing `scripts/generate_command_docs.py` rather than hand-editing the generated file. The same regeneration also touched `GEMINI.md` as an unrelated side effect — the known, still-open stale-revert bug (#884/#899) — which was discarded rather than committed.

All three tasks passed two-stage review (spec compliance, then code quality) with no fix loops needed; diffs matched the plan's given code exactly. Final suite: 1879 passed, 2 skipped.

## New goalpost

With `job_terminal` and `review_submitted` now event-observable, `synlynk events tail` gives this week's manual autopilot-lite loop run (Week-1 item 3) something concrete to watch without querying `state.db` directly. No consumer subscribes to either new event type yet — that stays Week 2's TPM/session MVP scope, per the program-design spec. The next steps on the Autonomous Ops Lite critical path are unchanged by this PR: pick a real synlynk goal and run the loop manually across synlynk + cc-videoreframing, ship v0.14.0 (this event-contract extension is one of its named line items), and measure the friction that run surfaces.
