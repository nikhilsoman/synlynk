---
title: "PR #2085 — gh:#1926: A Migrations Framework, and Burying 11,384 Dead Shards"
date: 2026-10-06
series: "Building the OS for Multi-Agent Development"
post: 254
pr: "#2085"
merged: null
author: "synlynk team"
version: "unreleased"
tags: [posts]
type: pr
---
# 254: gh:#1926 — A Migrations Framework, and Burying 11,384 Dead Shards

PR: [#2085](https://github.com/nikhilsoman/synlynk/pull/2085)

## Where we left off

gh:#1926 was filed as an architecture roadmap item: "single workspace-owner DB, DAO + unit-of-work transactions, migrations; SQLite becomes canonical, Markdown becomes a verified generated export." It had been sitting blocked behind two other pieces of work — gh:#1921 (state+worktree GC) and gh:#1924 (dispatch_agent/HarnessAdapter decomposition) — both of which closed earlier this cycle, unblocking it. Separately, gh:#1831 had already documented 11,384 dead `state.db` shards (6.1GB) sitting under `~/.synlynk/projects/<cwd-hash>/state.db`, left behind by a CWD-hash-keyed path bug that `product_store.py` had since fixed. #1926 was the natural place to also clean that up, since the Empirical Capability Assessment Policy (`CLAUDE.md`, 2026-10-04) explicitly names this shard sprawl as the reason `capability_ratings`/`cost_entries` can't be aggregated reliably yet — this work directly unblocks gh:#1993 (capability report generation).

## What moved the goalpost

The brainstorm for this PR found that most of #1926's original body was already done. `product_store.py` already resolves a single canonical, slug-keyed workspace DB path and already promotes legacy per-repo DBs into it via SQLite's online backup API. The Markdown generators in `db.py` were already read-from-SQLite, write-Markdown — not a second source of truth. A direct query against the live canonical DB confirmed `cost_entries` and `capability_ratings` were healthy and actively written. So the DAO/unit-of-work layer #1926 originally asked for had no second data source left to coordinate — adding one would have been pure YAGNI.

That re-scoping narrowed this PR to the two pieces that were genuinely still missing: a real migrations framework (replacing `db.py`'s monolithic `_migrate_db`), and the one-off cleanup script for #1831's shard debris. Both pieces were independent — they touch disjoint files with no shared dependency — so this was dispatched as two parallel components rather than one sequential implementation, per the standing instruction to use `superpowers:subagent-driven-development` routed through real dispatch rather than generic subagents.

## What this PR shipped

**Component 1 (dispatched to Codex, `job-0c49e1eb`, refactor/cli-plumbing lane):** a new `synlynk/migrations/` package. `Migration` is a frozen dataclass (`version: int, name: str, up: Callable[[sqlite3.Connection], None]`). Each migration is its own module (`m0001_initial.py`, `m0002_...`), exporting a module-level `MIGRATION = Migration(...)`. `migrations/runner.py`'s `run_pending_migrations(conn)` reads `PRAGMA user_version`, walks a static explicitly-imported registry in ascending version order, runs each pending migration in its own transaction, and records it in a new audit-only `migration_history` table (`version, name, applied_at`) — `PRAGMA user_version` stays the control-flow source of truth; the audit table just answers "when did column X get added" without `git blame` archaeology. `db.py`'s old `_migrate_db(conn)` (previously 877-980, one monolithic function) became `_run_legacy_migration_and_repairs` plus a thin wrapper calling `run_pending_migrations` — a pure decomposition, no SQL content changed, same call site. The unlock: each migration step is now independently testable at `user_version = N-1`, instead of requiring the full chain from version 0.

**Component 2 (dispatched to Grok, `job-988e9a2e`, infra-scaffold lane):** `scripts/cleanup_legacy_project_shards.py`, a one-off (not a `synlynk` subcommand) remediation script for the #1831 shards. It globs `~/.synlynk/projects/*/state.db`, checks each file's `mtime` against a default cutoff of 2026-09-16 (one day after #1831's confirmed-inert date), and defaults to dry-run: print a summary, write the candidate-for-deletion list to a report file, touch nothing. `--execute` is required to actually delete, and even then only shards that passed the mtime safety check — anything newer is excluded and reported separately, regardless of `--execute`. No archival step was needed here, unlike the standing archive-before-branch-removal policy for unmerged work — these are three-week-dead cache shards, confirmed inert by #1831 itself, not in-progress work.

Both components shipped with tests seeded against their own isolated fixtures (in-memory SQLite at `version - 1` for migrations; a temp directory of fake shard files at varying mtimes for cleanup) — 66 tests passing combined after merge, with no regressions against the existing migration/onboarding test suites.

One notable snag during review, not in the code: both dispatched jobs surfaced as `FAILED (exit 1)` in `synlynk jobs`, despite each agent's own turn ending cleanly (`stopReason: end_turn`) and all tests passing. Direct queries against `state.db`'s `daemon_jobs`, `job_terminal_decision`, and `job_status_shadow` tables traced this to a pre-existing, unrelated bug: a post-task cost-logging step throwing `OperationalError: table cost_entries has no column named pr_number`, compounded by the newer job-truth reconciliation layer not yet knowing how to map the legacy `unpushed_branch` status (`reason_code: legacy_status_unmapped`). This is exactly the discipline the project's own memory already encodes — "never trust `synlynk jobs` status alone" — and it held up again here: both components' actual work was sound; the red status was a side effect of infrastructure plumbing in cost capture, not a defect in either implementation.

## What's next on the capability-report track

With the migrations framework in place and the shard sprawl cleared, the remaining blocker on gh:#1993 (capability report generation) and the broader Empirical Capability Assessment Policy is no longer scattered state — it's building the actual `synlynk capability report` query surface over the now-consolidated `capability_ratings`/`cost_entries` tables. The cost-capture schema bug surfaced during this PR's review (`cost_entries` missing `pr_number`) is a separate, pre-existing issue worth tracking on its own, since it affects provenance backfill for every dispatched job, not just this one.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
