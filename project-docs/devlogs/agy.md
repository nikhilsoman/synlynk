# Agy Devlog

## 2026-06-28 — Homepage Sections 1, 3, 4, 5 & CSS Design System (Phase 2)

### Shipped
- Modularized repeated card components into Nunjucks macros (`website/src/_includes/macros.njk`).
- Implemented Section 1 (Tagline Hero) porting layout from `hero-v4.html` with class-based colors (no inline styles).
- Implemented Section 3 (Relief Section) using cards and the distributed cost savings callout.
- Implemented Section 4 (How It Works) command flow using cards.
- Implemented Section 5 (Features spotlight) 2x2 grid with commands and keyword tags.
- Extended `website/src/assets/css/main.css` to add support for all new visual components (buttons, gradients, cards, and terminal window styling).
- Fixed the footer docs link in `base.njk` to point to the absolute `/#docs` path.
- Verified successful Eleventy build in the worktree.
- Authored Phase 2 blog post at `docs/blog/30-pr-bs5-phase2-website-redesign.md`.

## 2026-07-03 — Architect Map (Task 5 of BS-21 Vizor)

### Shipped
- Implemented `generate_tube_html(data, port)` in `synlynk/viz.py`.
- Implemented centered setup-prompt card matching spec if `tube_config` is None, using premium CSS styles.
- Implemented custom SVG generation in Python when `tube_config` is present:
  - Generates line segments from coordinate lists.
  - Generates station circle elements with radius based on connection count: `r = 4 + (segs * 2)`.
  - Computes station connections dynamically based on lines list.
  - Generates multi-color interchange hub rings dynamically using segmented stroke-dasharray/stroke-dashoffset circles.
  - Generates assignment badges for agents (Claude, Agy, Codex, Grok) at `y - r - 10`.
  - Supports custom label alignments (top, bottom, left, right) and multi-line label rendering (split by newline).
  - Integrates hover tooltips showing station name and description from config.
  - Supports zoom-in and zoom-out operations on the SVG canvas.
- Added comprehensive unit tests in `tests/test_viz.py` for both setup-prompt and configured states.
- Verified successful cache generation with `python3 bin/synlynk.py viz --generate`.

## 2026-08-13 — Non-authoring PR Review & Merge for PR #926 (A3: Home/Headless Detection, #740)

### Shipped
- Reviewed PR #926 (`dispatch/codex/job-08ce0867`): verified `dispatch.py` `_dispatch_context()` helper (`sys.stdin.isatty()` with `except -> headless` fallback), `daemon.py` and `scheduler.py` hardcoded `'headless'` annotations, and 4 unit tests in `tests/test_agent_quota_tracking.py`.
- Ran `synlynk pr check` and confirmed all 71 tests in `tests/test_agent_quota_tracking.py` pass cleanly.
- Posted formal COMMENT review per PR Review Discipline and #423 identity rule.
- Merged PR #926 into main via `gh pr merge --squash`.

## 2026-08-31 — Phase 4: Database Schema Dual-Read / Dual-Write (#1307 / PR #1311)

### Shipped
- Implemented Phase 4 database schema dual-read/dual-write separating compute harnesses (`claude`, `codex`, `grok`, `agy`, `local`) from workspace agent roles (`pm`, `architect`, `tpm`, `dev`, `designer`, `qa`, `marketing`).
- Bumped `_DB_MIGRATION_VERSION = 3` with automatic column additions (`harness`, `role` in `daemon_jobs`; `harness`, `agent_role` in `cost_entries`), backfill migrations, and indexes.
- Added `get_costs_by_harness()` and `get_costs_by_agent_role()` query helpers to `synlynk/db.py`.
- Threaded dual-writes through `dispatch_agent()`, `_reconcile_jobs()`, `_reconcile_daemon_jobs()`, `update_costs()`, and `_insert_cost_row()`.
- Unified SQLite connection management in `dispatch_agent()` preventing database lock contentions during single-threaded capability sweeps and quota gating.
- Authored blog post `docs/blog/144-pr1311-phase4-db-schema-dual-read-write.md`.
- Verified entire 2,405-test suite passing. PR #1311 reviewed by Codex (`job-abd04554`), CI passed, and merged into `main`. Closed issue #1307.

## 2026-09-02 — Fleet Parity: Add Grok to agent_slots in Default Config Templates (#863 / PR #1327)

### Shipped
- Added `grok` to `defaults["agent_slots"]` in `synlynk/__init__.py:load_config()`, ensuring runtime config fallback contains all 4 Core Fleet harnesses (`claude`, `agy`, `codex`, `grok`).
- Verified diagnostic profile validation (`_hc_agent_profiles`) in `synlynk doctor` and CLI slot resolutions recognize Grok consistently across initialized and uninitialized environments.
- Added comprehensive unit test in `tests/test_agent_cli.py` and updated `test_load_config_has_new_defaults` in `tests/test_synlynk.py`.
- Authored design spec `docs/superpowers/specs/2026-09-02-agent-slots-grok-design.md`, implementation plan `docs/superpowers/plans/2026-09-02-agent-slots-grok.md`, and blog post `docs/blog/156-pr1327-agent-slots-grok.md` indexed in `docs/blog/README.md`.

## 2026-09-02 — Sentinel Guard: Token Bloat & Cost Inflation Detection (#1073 / PR #1334)

### Shipped
- Investigated root cause of anomalous token and cost bloat on `job-cf837848` ($5.26 / 7.6M input tokens on issue #1068). Identified `--context-mode full` monotonic context expansion across multi-turn headless stall without code modification.
- Implemented `check_token_bloat()` in `synlynk/sentinel.py` with configurable thresholds (`500k` tokens for 0 files touched, `500k` tokens/file ratio, `$3.00` WARN / `$5.00` CRITICAL cost inflation).
- Wired token bloat and cost inflation checks into `_reconcile_jobs()` and `_reconcile_daemon_jobs()` in `synlynk/jobs.py` and `check_sentinel_patterns()` in `synlynk/sentinel.py` with `.synlynk/telemetry.json` fallback scanning.
- Exported `check_token_bloat` in `synlynk/__init__.py`.
- Added unit tests in `tests/test_sentinel.py` and regression test `test_investigate_rootcause_costtoken_bloat_on_jobcf837848_and_add_costratio_sentinel_guard_1073` in `tests/test_agent_cli.py`.
- Authored design spec `docs/superpowers/specs/2026-09-02-token-bloat-sentinel-guard-design.md`, plan `docs/superpowers/plans/2026-09-02-token-bloat-sentinel-guard.md`, and blog post `docs/blog/160-pr1334-token-bloat-sentinel-guard.md` indexed in `docs/blog/README.md`.

## 2026-09-04 — Non-authoring PR Review & Merge for PR #1415 (Job status truth regression, #1414)

### Shipped
- Reviewed PR #1415 (`dispatch/codex/job-be18ebe7`), closing issue #1414.
- Ran `synlynk pr check` from within the PR's own worktree (`worktrees/job-be18ebe7`); confirmed all model versions attested and no blocking drift.
- Verified test suite: `pytest tests/test_agent_cli.py -k 'job_status_add_realghwrite_endtoend_regr' -v` (all 4 scenarios `pr_open`, `killed_zombie`, `timed_out`, `review_posted` passed cleanly in 3.07s).
- Verified the fake-gh subprocess end-to-end regression genuinely exercises the full job-status truth pipeline:
  - Spawns `fake-harness` and `fake-gh` as real child subprocesses via `dispatch_agent` and awaits process exit cleanly.
  - Verifies ground truth against `fake-github.json` state transitions.
  - Genuine path-specific reconciliation: `pr_open` scalar state, `killed_zombie` leaked worktree rescue (#1385), `timed_out` dead PID rescue (#1387), `review_posted` list verification (#1386).
  - Verifies storage convergence between `daemon_jobs` SQLite and `jobs.json` (#1388).
- Submitted formal approval review via `gh pr review 1415 --approve` as `synlynk-synlynk-qa[bot]`.
- Squash-merged PR #1415 into `main` via `gh pr merge 1415 --squash --delete-branch`, successfully closing issue #1414.
