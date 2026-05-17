# Changelog

All notable changes to synlynk are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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

[Unreleased]: https://github.com/nikhilsoman/synlynk/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/nikhilsoman/synlynk/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/nikhilsoman/synlynk/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/nikhilsoman/synlynk/releases/tag/v0.1.0
