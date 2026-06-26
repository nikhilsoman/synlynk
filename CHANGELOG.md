# Changelog

All notable changes to synlynk are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.9.7] - 2026-06-26

### Added
- **Grok as a first-class fourth agent peer** alongside claude/agy/codex across all synlynk subsystems
- `AGENT_CAPABILITY_BASELINES["grok"]` — cli, non_interactive_flags (`-p`), prompt_via_arg, dispatch_flags
  (`--always-approve`), roles (builder/architect), strengths
- `AGENT_DISCOVERY_DEFAULTS["grok"]` — discovery path `~/.grok`
- `_probe_model_version` — `grok -v` probe + `grok-[\w.-]+` version pattern
- `GROK.md` template — identity (`Co-Authored-By: Grok <noreply@x.ai>`), branch prefixes
  (`feat/grok/`, `fix/grok/`), standard session/worktree/live-issues sections, `synlynk:start/end` markers
- `_INSTRUCTION_TARGETS` + `_MARKER_STYLE_FOR_TOOL` entries for GROK.md
- Init wizard: GROK.md in `trio_content` + `_agent_guards`; `agent_slots` default expanded to four agents;
  `--agents` default updated to `claude,agy,codex,grok`
- `_inject_grok_rules()` — prepends `--rules GROK.md` for all grok exec calls; adds
  `--rules .synlynk/context.md` in headless (`-p`) mode; silently skips missing files
- `dispatch_agent()` — `--always-approve` → `--permission-mode bypassPermissions` fallback via
  agent profile `always_approve_unsupported`; `--output-format json` for grok headless dispatch
- `extract_tokens()` — nested `usage.input_tokens/output_tokens` pattern for Grok JSON output
- `extract_model_version()` — tier-2 path via `.agents/grok.json` `"model"` field
- `GROK.md` written to the synlynk repo itself (100 lines, markers bookending)
- 15 new tests covering all registration, instruction file, init wizard, exec injection, dispatch,
  and token/model extraction paths

### Fixed
- Stale time-sensitive fixture in `test_collect_capability_drop_returns_finding` — hardcoded
  2026-06-21 timestamps replaced with `datetime.now(timezone.utc)`-relative values

---

## [0.9.3] - 2026-06-23

### Added
- `SynlynkDaemon` class — subclasses `WatchDaemon` to add an embedded HTTP server thread on
  `localhost:27471` and persistent job dispatch on every poll tick; double-fork daemonization
  inherited from `WatchDaemon`; separate pidfile `.synlynk/daemon.pid` and log `.synlynk/daemon.log`
- `daemon_jobs` table in `state.db` — persistent job queue with `priority` (1–10), `depends_on`
  (JSON array of job IDs), and full status lifecycle `queued → running → done | failed`
- `_reconcile_daemon_jobs()` — reaps finished child processes using `os.waitpid(WNOHANG)` (zombie-safe),
  reads `.exit` files for exit codes, updates `status`/`exit_code`/`completed_at` in state.db
- `_dispatch_ready_jobs(max_parallel)` — launches queued jobs respecting concurrency cap and dependency
  chains; propagates `failed` status to downstream dependents immediately; commits per-job for
  crash-safe restart semantics
- HTTP API on `localhost:27471` — 10 endpoints: `GET /context`, `GET /status`, `GET /jobs`,
  `GET /jobs/<id>`, `POST /dispatch`, `GET /stories`, `GET /stories/<id>`, `GET /capability`,
  `GET /sentinel`, `POST /checkpoint`; `_ReuseAddrHTTPServer` subclass prevents `Address already
  in use` on rapid restart; `threading.Lock` guards concurrent `generate_context()` calls
- `synlynk daemon start|stop|status|restart` CLI command
- `synlynk daemon --install-service` — writes and activates platform service unit:
  macOS: `~/Library/LaunchAgents/com.synlynk.daemon.plist` via `launchctl load -w`;
  Linux: `~/.config/systemd/user/synlynk-daemon.service` via `systemctl --user enable --now`;
  Fallback: `@reboot` crontab entry
- `synlynk daemon --uninstall-service` — reverses each platform path; handles `FileNotFoundError` gracefully

### Fixed
- Daemon zombie process detection: replaced `os.kill(pid, 0)` with `os.waitpid(WNOHANG)` so
  exited child processes are properly reaped rather than staying `running` indefinitely
- Dependency deadlock: queued jobs whose dependency fails are immediately marked `failed` rather
  than staying queued forever
- Transaction isolation in dispatch: each launched job is committed individually so a crash
  mid-loop cannot produce duplicate spawns on restart

---

## [0.9.2] - 2026-06-22

### Added
- `synlynk join` — new member onboarding: seeds a devlog stub for the joining user, regenerates
  AI context files (CLAUDE.md, GEMINI.md, AGENTS.md) with the joining member's identity, and
  prints a team digest showing all active members and their recent focus areas
- `synlynk team status` — team digest view: lists all members with devlog presence, current
  story assignments, token budget consumption, and last-active timestamp; reads
  `project-docs/devlogs/<user>.md` across all contributors
- `synlynk decide <topic> --panel <agents>` — multi-agent consensus panel: dispatches the
  panel agents non-interactively with the same decision prompt, collects structured
  `DECISION:` blocks from each response, computes a consensus position, and optionally
  writes a signed `Decision` record to `project-docs/decisions/YYYY-MM-DD-<topic>.md`
  with `--record` flag
- `--tokens <N>` flag on `synlynk story create` — set an estimated token budget for a story;
  stored in new `estimated_tokens` column on the `stories` table
- `_seed_devlog(username, root)` helper — writes a devlog stub for the joining user with an
  initial entry so the devlog file exists and is attributable in team digests from day one
- `_generate_ai_context_files(username, root, config)` helper — regenerates CLAUDE.md,
  GEMINI.md, and AGENTS.md with the joining member's name in the `git config user.name` slot
- `_build_team_digest(root)` helper — reads all devlogs from `project-docs/devlogs/`, extracts
  last-active date and focus summary per member; used by both `join` and `team status`
- `_check_upstream_divergence(root)` helper — checks whether the local branch is behind the
  remote before any write to `project-docs/`; prints a warning with advice to `git pull` if
  divergence is detected; continues without blocking so offline workflows still function
  (pull-before-write arbitration)

### Fixed
- None in this release

---

## [0.9.1] - 2026-06-22

### Added
- `--docs-dir <path>` flag on `synlynk init` — override the default `project-docs/` location
  for repos that store docs elsewhere (e.g. `--docs-dir docs/project`)
- `_docs_dir(root, config)` helper — reads `docs_dir` from `.synlynk/config.json`, falls back
  to `project-docs/`; used by `exec`, `checkpoint`, `status`, and `init` so every command
  respects the configured docs location

### Fixed
- Installed binary (`~/.synlynk/bin/synlynk`) crashed with `ModuleNotFoundError: No module
  named 'synlynk'` when invoked outside the source repo after the v0.9.0 package split.
  Fixed by embedding the package `synlynk/` directory in `~/.synlynk/lib/synlynk/` at install
  time and prepending `$HOME/.synlynk/lib` to `sys.path` in the installed shim.
- `synlynk init` in a repo with existing `project-docs/` overwrote the existing docs with
  blank templates. Fixed by detecting existing files via `_find_existing_doc()` and migrating
  their content to the new location (or skipping write if no relocation is needed).

---

## [0.9.0] - 2026-06-21

### Added
- Scoped dispatch context: `exec` now injects a per-task section (`## Current Task`) with
  only the relevant plan block instead of the full devlog, reducing context window usage
- `## Relevant Files` injected per dispatch from the source map — derived from the task
  description matched against `source-map.md` symbols
- `## How to Verify` contract injected per dispatch — specifies acceptance criteria the agent
  should validate before declaring the task done
- Per-agent prompt framing: Claude, AGY, and Codex each receive a tailored preamble that
  matches their CLI interaction model (conversational vs. task-oriented vs. non-interactive)
- Ed25519 capability rating signing: every `capability_ratings` row is signed with the project
  key so ratings cannot be forged across project boundaries
- Anti-gaming quality cap: `test_count < 3` stories are capped at quality score 5.0 regardless
  of other signals, preventing artificially inflated ratings for untested work
- `synlynk/` package split: all ~5000 lines of application logic moved from `bin/synlynk.py`
  into `synlynk/__init__.py`; `bin/synlynk.py` becomes a 5-line import shim

### Fixed
- `capability_ratings` entries were not being attributed to the correct project when multiple
  synlynk-managed repos shared the same `~/.synlynk/` directory — Ed25519 project key now
  scopes all ratings correctly

---

## [0.8.0] - 2026-06-21

### Added
- `synlynk agent run` — foreground support engineer investigation: collects signals, formats a
  structured report, and offers to file a GitHub issue or draft a fix PR
- Five signal collectors for the support engineer archetype: failing tests, flaky tests,
  coverage gaps, stale dependencies, open GitHub issues exceeding age threshold
- 7-day and 30-day deduplication: signals already filed within the window are suppressed so
  the agent doesn't file duplicate issues on repeated runs
- `synlynk agent --install-cron` — registers a launchd plist (macOS) or systemd timer
  (Linux) that runs the support engineer agent on a configurable schedule
- `.agents/` config directory: `support-engineer.json` defines signal weights, age thresholds,
  and notification channels per project; read by `synlynk agent run` at startup
- GitHub issue filing via `gh issue create` with structured body including signal summary,
  affected files, and suggested fix skeleton
- Draft fix PR creation via `gh pr create` for issues with high-confidence fix candidates

---

## [0.7.0] - 2026-06-20

### Added
- `synlynk scan` / `synlynk scan --deep` — language-agnostic source scanner: reads file tree,
  extracts top-level symbols from Python/JS/TS/Go/Rust/Ruby/Java/C/C++ source, writes
  `source-map.md` and populates `source_symbols` table in `state.db`
- `## Source Architecture` section injected into every `exec` context from the cached scan
  result, giving agents a structural overview without reading individual files
- Passive git-HEAD cache: scan results are keyed to the current git HEAD SHA; a re-scan is
  only triggered when HEAD changes, not on every `exec` call
- `synlynk scan --status` — shows last scan timestamp, HEAD SHA, and symbol count without
  re-scanning
- Dual storage: symbols written to both SQLite `source_symbols` table (queryable) and
  `source-map.md` (human-readable, injected into agent context)
- Language detection by file extension with fallback to content heuristics

### Fixed
- `synlynk scan` no longer traverses `.git/`, `node_modules/`, or `.synlynk/` directories

---

## [0.6.1] - 2026-06-17

### Added
- Instruction reach to seven additional IDE/editor targets: Cursor (`.cursor/rules/`),
  GitHub Copilot (`.github/copilot-instructions.md`), Windsurf (`.windsurfrules`),
  Cline (`.clinerules`), Aider (`.aider.conf.yml`), Continue (`.continue/config.json`),
  and Sourcegraph (`.sourcegraph/memory.md`)
- SHA manifest (`instructions.json`) tracking the synlynk-managed section hash for each
  generated file; used for drift detection
- Runtime drift detection: `exec` warns if any tracked instruction file's section has been
  externally modified since last generation
- `synlynk instructions status / diff / update / ack` — manage instruction file state
- Task status model: 5 states (`active`, `done`, `deferred`, `superseded`, `absorbed`);
  deferred tasks are included in context with reduced weight; `checkpoint` archives resolved
  states to a separate section
- AGY CLI replaces Gemini CLI throughout: all references to `gemini` updated to `agy`
- VERSION synced to GitHub releases (was incorrectly stuck at 0.4.x)
- `DB_PATH` centralised to `~/.synlynk/projects/<git-root-hash>/state.db` so the database
  is shared across worktrees of the same project

---

## [0.6.0] - 2026-06-14

### Added
- Model version tier-2 probe: `discover_agents()` now probes for Opus/Sonnet/Pro variants in
  addition to the base model, annotates capability entries with `model_tier`
- `synlynk pr check` — validates that the current branch's diff satisfies the story's
  acceptance criteria before opening a PR; exits non-zero if criteria unmet
- `synlynk score attest` — manually attest a story's quality score with a signed reason;
  appended to `capability_ratings` with `attestation=true` flag
- Verifier pipeline output capture: `run --trio` now captures and surfaces the Verifier
  agent's structured review comment
- Tokq `org_domain_tags` capability dimension: stories can be tagged with domain taxonomy
  labels (`backend/api`, `frontend/ui`, etc.) for cross-project capability aggregation
- Constraint propagation: blocking story constraints propagate to child tasks; dispatching a
  child task for a blocked story emits a warning and requires `--force`

---

## [0.5.0] - 2026-06-14

### Added
- SQLite WAL state database (`~/.synlynk/projects/<hash>/state.db`) replacing the flat JSON
  job store; WAL mode enables concurrent reads from multiple agent processes
- Model-aware routing: `dispatch` selects agent by matching story domain tags against
  `capability_ratings`; no domain match falls back to round-robin
- 3D domain taxonomy for capability rating: `(agent, domain, model_tier)` composite key
  replaces flat per-agent scores
- Quality signal hierarchy: test coverage, PR review comments, story completion rate, and
  task duration all feed the capability score; weights configurable in `.synlynk/config.json`
- `synlynk story create <title>` — create a new story in `state.db` with optional domain,
  priority, and acceptance criteria
- `synlynk story list` — list stories with status, domain, assignee, and capability score
- `synlynk score` — print capability score breakdown for all agents across all domains

---

## [0.4.2] - 2026-06-17

### Added
- Task status model (`active` / `done` / `deferred` / `superseded` / `absorbed`) added to
  the context schema; deferred tasks included in `context.md` with a `[deferred]` prefix
- `checkpoint` archives all resolved-state tasks to a `## Resolved Tasks` section rather than
  deleting them — preserves decision history while keeping the active list clean
- Agent instruction templates updated to explain the 5-state model and checkpoint archival

---

## [0.4.1] - 2026-06-17

### Added
- Section marker system: synlynk-managed blocks in instruction files delimited by
  `<!-- synlynk:start -->` / `<!-- synlynk:end -->` markers so user customisations outside
  those markers are preserved on regeneration
- SHA manifest (`instructions.json`): tracks content hash of the synlynk section in each
  generated file; used for drift detection
- `synlynk instructions status / diff / update / ack` — full CLI for managing instruction
  file drift
- `DB_PATH` centralised: all state now written to `~/.synlynk/projects/<git-root-hash>/`
  rather than `.synlynk/` within the project, so the database is shared across all worktrees
  of the same project

### Fixed
- `init` no longer regenerates files that already contain a synlynk section — protects user
  customisations from accidental overwrite

---

## [0.4.0] - 2026-06-14

### Added
- `AGENT_CAPABILITY_BASELINES` — hardcoded capability dict for claude/gemini/codex/agy with
  `cli`, `non_interactive_flags`, `roles`, and `strengths` per agent
- `discover_agents(config)` — probes each known agent CLI with `--version`, returns functional
  agents with their roles and capabilities; supports per-project path overrides via config
- `_static_scan(root)` — reads git log, README, and file tree to produce a structured project
  context dict (project name, commit count, languages, recent topics)
- `_write_informed_skeleton(scan)` — writes project-docs/ first draft using scan results
  instead of blank placeholders
- `_llm_enrich(agent_name, agent_cli, scan)` — opt-in step that calls the best available agent
  non-interactively to synthesise an informed `roadmap.md` from scan results
- `init()` refactored to a 6-step wizard: scan → **Magic Moment 1** (workgroup discovery table
  showing all detected agents with roles) → doc bootstrap → LLM enrichment offer → cloud nudge
  → finalise config
- `dispatch_agent(agent, task, story_id)` — launches agent CLI in background using
  `subprocess.Popen(start_new_session=True)`, captures stdout to `.synlynk/logs/<job_id>.log`,
  writes PID and job metadata to `.synlynk/jobs.json`
- `_load_jobs()`, `_save_jobs(jobs)` — read/write `.synlynk/jobs.json`
- `_reconcile_jobs()` — probes PIDs of running jobs via `os.kill(pid, 0)` on every startup;
  marks unreachable PIDs as failed/completed; called as first action in `main()`
- `synlynk dispatch <agent> --task <text> [--story <id>]` — **Magic Moment 2**: fire and
  forget agent dispatch from any shell
- `synlynk jobs [--all]` — list running/recent jobs with status, agent, and task
- `synlynk logs --job <id> [--tail N]` — tail the log file for a job
- `synlynk shell [--story <id>]` — open an interactive agent shell with story context injected
- `synlynk launch <agent> [--story <id>]` — interactive launcher that prompts for task before
  dispatching
- `synlynk run --trio <task>` — dispatches the same task to all functional agents in parallel
  (Architect, Builder, Verifier roles)
- ANSI colour helpers (`_BOLD`, `_GREEN`, `_YELLOW`, `_CYAN`, `_DIM`, `_RESET`) for wizard UI

### Fixed
- `_reconcile_jobs()`: `PermissionError` from `os.kill(pid, 0)` means the process exists (owned
  by another user) — no longer crashes the CLI; job correctly stays `running`
- `_reconcile_jobs()`: empty `log_file` no longer accidentally reads/deletes an unrelated
  `.exit` file in the current working directory
- `_llm_enrich()`: baselines now indexed by canonical agent name (not CLI binary path), so
  custom CLI paths still resolve the correct non-interactive flags

### Infrastructure
- 5 new reconcile/enrich tests; 4 new E2E tests (dispatch, jobs, logs, reconcile startup)
- 188 tests total (up from 140)

---

## [0.3.0] - 2026-06-03

### Added
- Enriched agent instruction templates: CLAUDE.md, GEMINI.md, AI_INSTRUCTIONS.md now include
  Live Issues SOP (Sev1/Sev2/Sev3 with RCA doc path pattern), Git Worktree-First Policy,
  per-agent branch naming and commit trailers, Mid-Session Anti-Amnesia Protocol (Phase 1/2
  cadence), Mandatory 4-Doc Discipline, and GitHub Projects v2 GraphQL integration block with
  parameterizable `PROJECT_ID`
- `AGENTS.md` — new Codex agent instruction file, generated at repo root on `synlynk init`
- `synlynk init --agents <claude,agy,codex>` — controls which agent files are generated
  (default: all three). Omit an agent to skip its file
- `synlynk init --mode <solo|team>` — writes `project-docs/.synlynk_config.json` with the
  chosen mode at init time (previously this file had to be created manually)
- `synlynk init --org <org>` — stores GitHub org name in `.synlynk/config.json`
- `synlynk init --repo <repo>` — stores GitHub repo name in `.synlynk/config.json`
- `synlynk init --project-id <id>` — fills GitHub Projects v2 node ID into all generated agent
  files, replacing the `TODO: PROJECT_ID` placeholder
- GEMINI.md includes AGY/Gemini CLI transition note: file is shared by Gemini CLI (until
  2026-06-18) and AGY CLI (AntiGravity) thereafter; no migration of the file is needed
- `_build_templates(org, repo, project_id)` internal function replaces the static `TEMPLATES`
  dict and `_SESSION_PROTOCOL` string, enabling parameterized template generation

### Changed
- `synlynk init` now writes `project-docs/.synlynk_config.json` directly (previously missing
  from init, requiring manual creation)

---

## [0.2.1] - 2026-05-17

### Fixed
- `exec_command()` now returns the child process exit code and `main()` calls `sys.exit()` with it — previously a wrapped command exiting non-zero would cause `synlynk exec` to exit 0, silently swallowing failures
- `parse_costs_md()` was reading the wrong column (`parts[6]` = Summary instead of `parts[5]` = Estimated Cost USD), causing `status` and budget checks to always report $0.00
- `install.sh` version corrected from `1.2.0-lite` to `0.2.0`
- `conftest.py` fixture schema aligned with real `costs.md` format (6-column) so budget tests exercise the correct parser behavior

### Removed
- Dead functions `log_telemetry()`, `extract_tokens()`, and `update_costs()` — superseded by `log_telemetry_event()` and manual cost tracking; removed to prevent confusion

### Infrastructure
- `.gitignore` expanded to cover `.synlynk/`, `__pycache__/`, `*.pyc`, `.DS_Store`, `test_archive/`, `test_context_output/`, `.venv/`
- `project-docs/roadmap.md` updated to reflect v0.2.x reality (was stale with v1.2/v1.3/v1.4 references)
- Test added for exit code propagation (47 tests total)

---

## [0.2.0] - 2026-05-17

### Added
- `synlynk watch start/stop/status` — background daemon that polls `project-docs/` and regenerates `context.md` on any file change, with configurable interval and debounce
- `synlynk checkpoint` — archives completed `[x]` tasks from `todo.md` into the user devlog, refreshes context, and emits a structured telemetry event
- `synlynk status` — project state dashboard showing active tasks, last checkpoint, sentinel alerts, budget, and watcher state; `--json` flag for machine-readable output
- `synlynk init --force` — overwrite existing template files
- `set_state()` — writes `.synlynk/state` and updates terminal title with state icon (`●` watching / `⚡` active / `○` stopped)
- Helper functions: `get_username()`, `get_mode()`, `load_config()`, `parse_costs_md()`
- `log_telemetry_event()` — structured event logging with `schema_version` and `type` fields
- `_check_costs_freshness()` — warns when `costs.md` has not been updated within the current session
- Devlog archiving: entries older than 30 days moved to `devlogs/archive/YYYY-MM.md`

### Changed
- `generate_context()` — now compacts output: excludes completed `[x]` tasks, includes only "In Progress" roadmap rows, injects sentinel alerts at top when present, scoped to last 7 days of devlog
- `check_budgets()` — now reads cumulative spend from `costs.md` instead of telemetry; request count sourced from telemetry `type=exec` events
- `check_flatline()` — now writes alerts to `.synlynk/sentinel.md` in addition to stdout
- `exec_command()` — uses `subprocess.Popen` (no stdout capture) for full TTY interactivity with Claude Code and Gemini CLI
- `CLAUDE.md` / `GEMINI.md` templates — include full session protocol: startup checklist, during-session rules, session-end steps
- `VERSION` bumped to `0.2.0`

### Fixed
- Type hint `str | None` replaced with `Optional[str]` for Python 3.8 compatibility (union syntax requires 3.10+)

### Infrastructure
- Added pytest test suite (`tests/conftest.py` + `tests/test_synlynk.py`) with 46 tests and `project_dir` fixture
- Added GitHub Actions CI workflow (runs pytest on Python 3.8, 3.10, 3.12 on push and PRs)
- Added `LICENSE` (MIT), `CONTRIBUTING.md`, PR template, issue templates

---

## [0.1.0] - 2026-05-14

Initial public release.

### Added
- `synlynk init` — bootstraps `project-docs/` (roadmap, todo, memory, costs, devlogs) and writes `CLAUDE.md`, `GEMINI.md`, `AI_INSTRUCTIONS.md`, `.cursorrules` and `.synlynk/config.json`
- `synlynk exec <cmd>` — wraps any AI CLI: injects context, checks budget, logs telemetry, detects flatline loops
- `synlynk upgrade` — checks GitHub releases API for newer versions
- `generate_context()` — compiles `project-docs/` into `.synlynk/context.md`
- `check_flatline()` — detects 3 consecutive failures of the same command
- `check_budgets()` — warns at 80% of configured USD/request limits
- `log_telemetry()` — rolling JSON log of last 100 exec events
- `install.sh` — global installer, adds synlynk to `~/.synlynk/bin/` and PATH

[Unreleased]: https://github.com/nikhilsoman/synlynk/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/nikhilsoman/synlynk/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/nikhilsoman/synlynk/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/nikhilsoman/synlynk/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/nikhilsoman/synlynk/releases/tag/v0.1.0
