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

## 2026-09-05 — Dynamic Home Harness Orchestrator Parity & Dual-Mode Directives (#1440 / PR #1440)

### Motivation & Root Cause Analysis
- Investigated systemic paralysis of non-Claude interactive home harnesses (specifically Agy, but also Codex and Grok).
- Identified root cause across 3 failure vectors:
  1. Static Markdown Directives encoded hardcoded subservience (`"Do not start a task outside your role column without explicit Claude approval"`), causing interactive harnesses to self-censor and refuse to drive lifecycle loops.
  2. The Genesis vs. Fluidity flaw: templates generated only at `init` fail when an operator switches home harnesses mid-stream on an existing repo.
  3. Absence of constitutional precedence: static files lacked a rule declaring active session runtime context as governing.

### Shipped
- **Goal & Governance:** Tracked under `goal-250b6fb2`. Authored comprehensive design spec and RCA at `docs/superpowers/specs/2026-09-05-dynamic-home-harness-orchestrator-parity-design.md` and TDD plan at `docs/superpowers/plans/2026-09-05-dynamic-home-harness-orchestrator-parity.md`.
- **Constitutional Precedence & Dual-Mode Instructions:** Updated `synlynk/instructions.py` across `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, and `GROK.md` with explicit Mode A (Home Conductor) vs. Mode B (Away Worker) directives and constitutional precedence clause.
- **Dynamic Runtime Home Detection:** Implemented `detect_active_home_harness()` in `synlynk/context.py` inspecting caller process tree, terminal environments, and config slots, rendering an authoritative runtime banner at the top of `.synlynk/context.md`.
- **`synlynk home` CLI Verb:** Implemented `synlynk home [harness]` in `synlynk/cli.py` and registered in `COMMAND_TAXONOMY` (`synlynk/taxonomy.py`), enabling zero-touch home harness switching and immediate context regeneration.
- **Legacy Directive Repair:** Purged hardcoded Claude-centrism from `_PR_REVIEW_SOP`, `_BRAINSTORM_SOP`, and `_CAPABILITY_ALLOCATION_SOP` in `synlynk/probe.py`. Enhanced `_repair_sops_only` to automatically detect legacy Claude references and upgrade them to Home Harness authority.
- **Verification:** Unit tests added in `tests/test_instructions.py`, `tests/test_context.py`, `tests/test_home_cmd.py`, and `tests/test_probe.py`. Full test suite passing (2584 passed).
- **PR & Review:** Pushed `feat/agy/dynamic-home-directives` and opened PR #1440; dispatched Claude (`architect` identity via `job-927d474f`) for non-authoring review.

## 2026-09-06 — Allow Distinct QA App Identities to Submit Approving PR Reviews (#1475)

### Root Cause Analysis
- Investigated issue #1475 where distinct provisioned QA App identities (`synlynk-synlynk-qa[bot]`) still produced `COMMENTED` reviews on human-authored PRs (#1474), leaving `reviewDecision=REVIEW_REQUIRED`.
- Discovered 3 core findings:
  1. `GET /user` (`gh api user`) returns HTTP 403 (`Resource not accessible by integration`) when authenticated as a GitHub App installation token. The App identity must be derived directly from `app_slug` (`synlynk-synlynk-qa[bot]`) rather than calling `gh api user`.
  2. Dispatched QA reviewers received prompts instructing them to post comment reviews because `AGENTS.md` and `GEMINI.md` contained legacy `#423` text claiming all agents share a single identity.
  3. `uxcore.approve_pr()` ran raw `gh pr review --approve` with ambient `os.environ`, ignoring role-scoped GitHub App tokens (`qa.token.json`).

### Shipped
- **Role Token Binding:** Updated `uxcore.approve_pr()` to resolve role-scoped GitHub tokens (`_resolve_dispatch_gh_token("qa")`) and pass `GH_TOKEN`, `GITHUB_TOKEN`, and `GH_CONFIG_DIR` in subprocess environments.
- **Tri-State Fallback Handling:**
  - Distinct QA App identities execute `gh pr review --approve` cleanly.
  - Same-identity collisions fall back to comment checklist (`same-login collision review fallback, see #423`).
  - Credential/Permission rejections (401/403) fall back to actionable comment checklist (`credential/permission review fallback, see #423`).
  - Unrelated / Network errors fail closed without posting spurious comments.
- **Subprocess Git Path Optimization:** In `synlynk/dispatch.py:_resolve_github_apps_dir()`, added early check for `.git` to avoid unnecessary `git rev-parse` subprocess calls in non-git test fixtures.
- **Probe Stale SOP Detection:** Updated `synlynk probe` stale SOP detection in `_repair_sops_only()` to catch legacy `#423` shared-identity text and upgrade directive templates to `qa APPROVE` defaults.
- **Regression Tests:** Added `test_allow_distinct_qa_app_identities_to_submit_approving_pr_reviews` in `tests/test_agent_cli.py` covering all branches.

## 2026-09-08 — Diagnose and Prevent Zombie Worker Termination (#1498)

### Root Cause Analysis
- Investigated issue #1498 where design and review dispatches (non-gh-write tasks) terminated after 3–5 minutes with status `killed_zombie` and exit code `-9`, destroying worker logs.
- Discovered 4 core failure modes:
  1. **Premature Zombie Reaping:** In `synlynk/jobs.py:_reconcile_daemon_jobs`, any worktree contains `.git`, so `has_leaked_worktree()` evaluated to True. When the worker process exited, it bypassed reading `{log_path}.exit` and ground-truth verification, unconditionally marking non-gh-write jobs as `killed_zombie` (-9) and deleting the worktree.
  2. **Worktree Log Loss:** `dispatch.py` placed `logs_dir` at `worktree/.synlynk/logs/`. When a zombie worktree was reaped, the worker log and exit marker were destroyed.
  3. **Offset-naive vs. Offset-aware Datetime TypeError:** In `synlynk/gh_verify.py` and `synlynk/jobs.py`, GitHub timestamps parsed as UTC-aware datetimes were compared against naive `started_at` datetimes, raising an unhandled `TypeError` that crashed the reconciler.
  4. **Unprotected Reconciler Loop Boundary:** `_reconcile_daemon_jobs` had a single `try` wrapping the entire loop over all jobs; an exception on any single job aborted reconciliation for all remaining jobs.
  5. **Relative `.pem` Key Path Resolution:** In `synlynk/github_app_auth.py`, relative `.pem` paths in app config failed when openssl ran with CWD set to a worktree.

### Shipped
- **Timezone-Aware Normalization & Exception Safety:** Added `_to_utc_dt()` in `synlynk/gh_verify.py` to normalize datetimes to timezone-aware UTC. Wrapped comparisons with `_compare_dt_lt` and added fallback in `_apply_gh_write_verification` in `synlynk/jobs.py`.
- **Absolute App Key Resolution:** Added `_resolve_private_key_path` in `synlynk/github_app_auth.py` to resolve private keys relative to `apps_dir` or `_daemon_state_path("github_apps")` regardless of process CWD.
- **Reconciler Exception Boundary:** Wrapped per-job iteration in `_reconcile_daemon_jobs` in a `try...except Exception as exc:` block to ensure one failing job cannot abort the daemon loop.
- **Persistent Central Logs & Reap Preservation:** Moved worker `logs_dir` in `synlynk/dispatch.py` to `_daemon_state_path("logs")` outside the disposable worktree. Enhanced `_reap_zombie_worktree` in `synlynk/jobs.py` to preserve any logs before worktree removal.
- **Correct Exit Resolution Order:** In `synlynk/jobs.py:_reconcile_daemon_jobs`, inspected waitpid and `{log_path}.exit` before evaluating zombie criteria. Jobs with exit status or work are classified as `done` / `failed` rather than `killed_zombie`.
- **Comprehensive Test Suite:** Added unit tests across `tests/test_gh_verify.py`, `tests/test_github_app_auth.py`, `tests/test_daemon_token_refresh.py`, `tests/test_dispatch.py`, and `tests/test_jobs.py`.



