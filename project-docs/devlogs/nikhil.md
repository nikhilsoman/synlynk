# Devlog - Nikhil Soman

## 2026-06-17
### Session: v0.4.1 Instruction Reach — PR #45, merged

- **Merged:** PR #45 (`feat/v0.4.1-instruction-reach`) — v0.4.1 Instruction Reach fully shipped
- **Method:** Subagent-driven development (session resumed from prior context). 10 TDD tasks. Final code review subagent (whole implementation), post-review fixes, R1 + R2 review cycles, then merge.
- **What shipped:**
  - **AGY cleanup:** `"gemini"` CLI removed from `AGENT_CAPABILITY_BASELINES`, `AGENT_DISCOVERY_DEFAULTS`, `_probe_model_version` probe commands, argparse help. `GEMINI.md` template now AGY-only (`agy-2.x`, no transition note). `agent_slots` `"agy":"gemini"` → `"agy":"agy"`.
  - **Section marker system:** Three styles — `html` (`<!-- synlynk:start -->` / `<!-- synlynk:end -->`), `hash` (`# synlynk:start`), `none` (synlynk owns whole file). `_extract_synlynk_section()` + `_compute_section_sha()` helpers.
  - **`_write_instruction_file(path, tool, content, marker_style)`:** Three-case logic — create (file absent), append (no markers), replace-section (markers found). SHA covers section content only — user edits outside markers never trigger false drift.
  - **Tool-native templates:** `_build_cursor_mdc()` (MDC frontmatter, `alwaysApply: true`), `_build_copilot_instructions()`, `_build_windsurf_rules()` (6-line hash-marked).
  - **`_INSTRUCTION_TARGETS`:** Single source of truth — 7 tracked files as `(path, tool, marker_style, detection_fn)`. Guards derived from `detection_fn` in `init()`; no duplicate `ext_guards` dict.
  - **SHA manifest (`.synlynk/instructions.json`):** Written by `init()` and `_write_instruction_manifest()`. Tracks per-file section SHAs.
  - **`init()` refactored:** Now writes all 7 targets; uses `_INSTRUCTION_TARGETS` for guards.
  - **`_check_instruction_drift()`:** Hooked into `exec_command()`. SHA-compares each manifest entry against current file. Fires `INSTRUCTION_DRIFT` sentinel, updates manifest SHA (deduplication — won't re-fire next exec).
  - **`synlynk instructions` CLI:** `status` (columnar table, 5 status values) / `diff` (user content outside markers) / `update` (re-generate + refresh manifest) / `ack` (remove INSTRUCTION_DRIFT from sentinel.md).
  - **`DB_PATH` fix (R1):** Moved from `.synlynk/state/state.db` (flat-file collision with v0.3.0 daemon state file) to `~/.synlynk/projects/<8-char-git-root-hash>/state.db`. All worktrees for a repo now share one DB (resolves worktree isolation bug).
  - **`isolated_db` autouse fixture (R1):** Added to `tests/conftest.py` — every test gets its own temp `state.db`; no cross-test DB pollution.
  - **Post-review fixes:** `ext_guards` dict eliminated from `init()` (guards now from `_INSTRUCTION_TARGETS[i][3]`); `AGENTS.md` added to `_AGENT_FILE_NAMES` (scan now surfaces it).
- **Tests:** 265 passing (34 new in `tests/test_instruction_reach.py`)
- **Blog post:** `docs/blog/13-v0.4.1-instruction-reach.md`
- **Roadmap:** v0.4.1 row added between v0.4.0 and v0.5.0, marked ✅ Shipped.

## 2026-06-14
### Session: v0.6.0 Job Control — R2 fix, merge PR #42

- **Merged:** PR #42 (`feat/v060-job-control`) — v0.6.0 Job Control + model-aware capability engine fully shipped
- **R2 critical bug fixed:** Tier resolution bypass in `_write_capability_rating()` — calling `extract_model_version(log_text, agent=agent)` fell through to Tier 3 (config default) when no synlynk-meta header present, then compared config default against live-probed `model_at_dispatch`, incorrectly setting `split_model=1` on normal single-model runs and silently excluding them from `capability_scores` aggregation.
  - Fix: extract Tier 1 only via `agent=None`, resolve hierarchy explicitly (Tier 1 > Tier 2 > Tier 3), flag `split_model=1` only when both Tier 1 and Tier 2 are concretely known and differ.
- **Also applied:** `quality_auto` normalization (`weighted_sum/total_weight`) from PR #44 — this branch predated that hotfix merge.
- **Tests:** 43 passing (2 new R2 regression tests)
- **Blog post:** `docs/blog/12-pr42-v0.6.0-job-control.md`
- **Roadmap:** v0.5.0 + v0.6.0 marked ✅ Shipped. Next: v0.7.0 async pipeline + daemon.

### Session: Quick Start Guide PDF Generation (v0.6.0)
- **Activity:** Designed and compiled a modern, minimalist Apple-style quick start guide covering all features of synlynk (up to v0.6.0).
- **Updates:**
  - Modified `docs/synlynk-quickstart-apple.html` to bump versioning to v0.6.0.
  - Refined Command Reference on Page 6: converted to a 2-column grid layout to fit `Story & Capability Scoring (v0.5.0/v0.6.0)` commands (`story create/list`, `score add/list`, `score attest`, `pr check`).
  - Replaced outdated "Hold off on dispatch..." warning callout on Page 6 to indicate that the Capability Engine and Smart Routing are fully live.
  - Marked v0.5 and v0.6 milestones as Live on Page 7 roadmap.
  - Generated PDF using headless Google Chrome at `docs/synlynk-quickstart-apple.pdf`.
  - Copied compiled PDF to root `synlynk_quick_start.pdf` and `docs/synlynk-quickstart-guide.pdf`.

### Session: v0.4.0 Hybrid Workgroup Bootstrap

- **Shipped:** v0.4.0 — 14 TDD tasks, 11 commits, 183 tests (PR #39, open)
- **Method:** Full subagent-driven development via `superpowers:subagent-driven-development`. Fresh subagent per task, spec + quality review after each. Session hit Claude rate limit mid-flight (Tasks 9-11 partial); resumed directly in main session.
- **Pre-implementation fix:** Tokq memory unit schema gap — redesigned from file-grain to 5 purpose-typed DB view units (`strategic`, `context`, `execution`, `activity`, `capability`). Visual in `docs/brainstorm/tokq-data-metamorphosis/`. Schema fix committed separately (PR #37, merged).
- **Bug caught in review:** `_reconcile_jobs()` was catching `PermissionError` alongside `ProcessLookupError` and marking jobs failed. `PermissionError` from `os.kill(pid,0)` means the process exists but is unsiglable — not dead. Fixed to `except ProcessLookupError:` only.
- **What shipped:**
  - `AGENT_CAPABILITY_BASELINES` (claude/gemini/codex/agy), job store constants, ANSI helpers
  - `_load_jobs()`, `_save_jobs()`, `_reconcile_jobs()` (PID probe on startup)
  - `_check_agent_functional()`, `discover_agents()` with configurable paths
  - `_static_scan()` (git log + README + file tree)
  - `_write_informed_skeleton()`, `_llm_enrich()` (opt-in, non-interactive)
  - `init()` refactored to 6-step wizard: scan → **Magic Moment 1** (workgroup table) → doc bootstrap → LLM enrichment offer → cloud nudge → finalise
  - `dispatch_agent()` with `start_new_session=True` background dispatch
  - `cmd_jobs`, `cmd_logs`, `cmd_shell`, `cmd_launch`, `cmd_run_trio`
  - Subcommand wiring in `main()` + 4 new E2E tests
- **Milestone:** First release where `synlynk dispatch claude --task "..."` actually works end-to-end. **Magic Moment 2** — parallel dispatch from shell — is now real.
- **Next:** v0.5.0 Capability Engine — SQLite WAL, data-driven capability routing, `synlynk migrate`.

## 2026-06-10
### Session: v0.3.1 Sentinel + Observability + E2E Test Suite

- **Discovery:** Upgraded installed synlynk from v1.2.0-lite → v0.3.0; found `extract_tokens()` and `update_costs()` were silently dropped in v0.3.0 TTY pass-through refactor. Confirmed v0.5.0 state.db spec explicitly depends on `extract_tokens()`.
- **Decision:** Insert v0.3.1 patch before v0.4.0 to restore regressions and harden the sentinel layer while the surface area was open.
- **Shipped:** v0.3.1 — 9 features, 40 new tests, 12 commits (PR #29, merged 2026-06-10):
  - `extract_tokens()` + `update_costs()` restored; tee-based stdout capture for non-interactive execs; cost pulse after each non-interactive exec
  - `WatchDaemon._health()` tri-state + `check_daemon_health()` ZOMBIE_DAEMON CRITICAL alert
  - `check_stall()` using `.synlynk/state` mtime + `exec_timeout_minutes` config key
  - `check_sentinel_patterns()` — flatline (existing) + success loop (new) + quota-exhausted (new)
  - `_check_pre_exec_gate()` — CRITICAL alerts block exec; `synlynk exec --force` bypasses
  - `_compute_burn_rate()` + burn rate / runway in `synlynk status`
  - Context bloat warning in `generate_context()` at 32 KB / 64 KB thresholds
  - `synlynk sentinel list/clear` CLI with structured `[SEVERITY] [TIMESTAMP] CODE:` format
  - VERSION bumped to 0.3.1 in `bin/synlynk.py` and `install.sh`
- **Shipped:** E2E test suite — 17 black-box CLI tests in `tests/test_e2e.py` (PR #30, merged 2026-06-10)
  - `Cli` helper class wraps subprocess calls; `cli` fixture provides initialized project
  - Covers: CLI basics, exec (exit codes, telemetry), sentinel CRUD, pre-exec gate, status
  - `pytest.ini` registers `e2e` mark; `pytest tests/` now runs 140 tests total
- **Method:** First full subagent-driven development session — 10 tasks, fresh subagent per task, spec + quality review after each. Caught 2 real bugs before PR: severity filter false-positive (substring → regex), dead `check_flatline()` left after rename.
- **Milestone:** `main` is now v0.3.1. Release checklist = `pytest tests/` (140 tests). v0.4.0 is next.

## 2026-06-07
### Session: Workspace & Multi-Repo Design

**Activity:** Third brainstorm session. Designed workspace concept (multi-repo support), machine-level identity, event-log team sync. Resolved the async drift concern that makes export/import unworkable at agentic velocity.

**Key Outcomes:**

1. **Workspace concept:** Unit of organization above a repo. One product = one workspace, N repos. Solo dev gets workspace with one member — invisible. `~/.synlynk/workspaces/<name>/state.db` is the single state store per product.

2. **Machine-level identity:** `~/.synlynk/identity.key` — one Ed25519 keypair per person per machine. Closes Gap 10 (network identity). Per-project keypair retired.

3. **Cross-repo Epics first-class:** One Epic spans repos. Stories have `repo_id` FK. Architect sees full cross-repo epic. Builder/Verifier sees workspace shared + repo slice.

4. **Event-log sync replaces export/import:** Daemon pushes new events to per-member branch in shared git repo every 5 min. Max drift ≈ 5 min — workable at agentic velocity. Becomes NATS at Tokq Alpha.

5. **Simulated team on one machine:** `git config user.name` switch — events record different git_user, all signed by machine key. Full cost attribution per simulated member. Enables Gaurav/Kunal simulation.

6. **Schedule impact:** workspace-aware init at v0.4.0, workspace join at v0.5.0, team attribution at v0.6.0, event sync at v0.7.0 (with daemon). Gap 10 closed.

**Spec committed:** `docs/superpowers/specs/2026-06-07-synlynk-workspace-multi-repo-design.md`

**PR opened:** https://github.com/nikhilsoman/synlynk/pull/28

---

### Session: Agent Identity, Dispatch & Entitlements + Arc Gap Analysis

**Activity:** Second major brainstorm session. Designed agent identity (two-layer: local Ed25519 + Role + Agent Profile), addressability (inbox table → NATS), dispatch architecture (4 modes), and entitlements (authorization + sandboxing). Followed with a milestone-wise gap analysis covering v0.4.0 through Tokq GA.

**Key Outcomes:**

1. **Identity is two-layered:** Local Identity (Ed25519 keypair, machine-scoped) answers "who made this decision." Role (Architect/Builder/Verifier) answers "what can this work touch." Agent Profile (CLI × model × environment × competency) answers "who fills this role best right now." These never mix.

2. **Ed25519 identity pulled forward from v0.9.0 to v0.5.0.** Every dispatch event and completion event is signed. Audit trail is non-repudiable at v0.5.0, verified by Tokq cloud at Tokq Alpha.

3. **Dispatch: 4 modes.** A=daemon (persistent, primary). B=self-chain (completion triggers re-evaluate). C=`synlynk dispatch` one-shot (universal fallback, CI/cron-compatible). D=agent-native scheduling (`use_native_scheduling` flag in agent_profiles). Fallback priority: A fails → C always works.

4. **Dispatch address → inbox table.** Logical address `synlynk://<project_id>/roles/<role>/inbox` resolves to state.db row today, NATS subject at v1.0. Forward-compatible scheme.

5. **Human-agent bridge is email, not dispatch.** Send-only SMTP at v0.7.0. Approval via `synlynk story approve <id>` CLI (not email reply). Gmail reply parsing deferred to v0.8.0.

6. **Entitlements: two layers.** Authorization (gate before dispatch — auto/approval/hold/reject). Sandboxing (constraints while running — token ceiling, time ceiling, network, path ACLs). Merge to main: always approval-required, no override.

7. **Gap analysis completed.** 12 gaps across v0.5.0–v1.0.0 identified. Priority: Gap 1 (v0.5.0 scope split) is the only blocker for next implementation plan. Gaps 2–4 (v0.6.0 design questions) can be resolved in one session.

**Specs committed:**
- `docs/superpowers/specs/2026-06-07-agent-identity-dispatch-design.md`
- `docs/superpowers/2026-06-07-arc-gap-analysis.md`

**Next:** Implement v0.4.0 (Trio Protocol — spec is ready). Then gaps 1–4 reconciliation session before v0.5.0 plan.

---

### Session: State DB & Agentic PM Design

**Activity:** Full brainstorm session. Diagnosed the merge conflict root cause (state branching with code), designed the state.db migration from project-docs/, and designed the full Agentic PM hierarchy as a consequence.

**Key Outcomes:**

1. **Root cause confirmed:** `project-docs/` tracked in git causes worktree snapshots to drift. The fix: state.db at `~/.synlynk/projects/<project_id>/` shared by all worktrees. Core invariant: state never branches.

2. **Agentic PM hierarchy locked:** Project → Arc → Phase → Epic → Story → Event. Arc is the strategic direction layer missing from all existing PM tools — handles pivots, convergences, and external triggers. Phase is structural backbone. Epic = one implementation plan. Story = one agent task with `done_criteria` and dependency graph. Event = append-only universal log replacing devlogs.

3. **Token budget as execution constraint:** `estimated_tokens` on stories replaces story points. Agent routing: capability score → quota headroom → cost. `agent_quotas` table tracks per-agent limits. Throughput = tokens/quota-period.

4. **Costs fully attributed:** `costs` table gains project FKs (`story_id`, `epic_id`, `phase_id`). Phase-level cost rollup now queryable.

5. **Platform sync:** `external_refs` table maps to GitHub/Jira/Linear. state.db is canonical; platforms are views.

6. **Schema verified against generate_context():** Three schema corrections found — memory uses `heading/body` (not key/value); tasks use `milestone` not `priority`; roadmap needs `os_layer` and `infrastructure` columns.

7. **Spec committed:** `docs/superpowers/specs/2026-06-07-synlynk-state-db-agentic-pm-design.md`

**Next:** Agent identity, addressability, scheduling, entitlements brainstorm.

---

## 2026-06-06
### Session: Unified Roadmap — OS Framing, Tokq Convergence, Tokq Gap Analysis

**Activity:** Full-day brainstorm + doc consolidation session. Scanned all proposals across the
repo, assessed competitive positioning vs. GStack/SuperPowers, converged the Tokq + synlynk vision,
designed the v0.4→v1.0 release staircase, absorbed the SQLite→NATS infrastructure arc, and closed
5 Tokq PRD requirement gaps.

**Key Outcomes:**

1. **Positioning locked:** "The OS for multi-agent development." Tier model (Solo/Team/Enterprise)
   retired. OS layer model replaces it — one product, increasing depth through 8 releases.

2. **Competitive positioning resolved:** GStack, SuperPowers, HermesAgent, OpenClaw, NmoClaw are
   Applications layer tools. synlynk is the OS they run on. Not competition. Coexistence via Open
   Context Protocol (two commands: `context --for` / `checkpoint --from`).

3. **Tokq convergence:** Recognized synlynk (May 2026) was the missing local OS client that Tokq
   (Jan 2026) always needed. Same author, same vision, different ends of the stack. Unified:
   synlynk = local OS, Tokq = cloud layer. Bridge at v1.0 via NATS leaf node.

4. **Release staircase designed (v0.4→v1.0):** 7 releases, each usable on its own, each unlocking
   one new capability. SQLite→NATS infrastructure arc absorbed into each release as the backbone:
   - v0.4: Conventions + Trio Bootstrap (IPC layer, flat files)
   - v0.5: Capability Engine (Scheduler, SQLite WAL)
   - v0.6: Job Control + Constraints (SQLite extended)
   - v0.7: Async Pipeline + Daemon (HTTP Context Server)
   - v0.8: Open Context Protocol (ecosystem interface)
   - v0.9: Review TUI + Team Safety + Agent Identity
   - v1.0: Stable OS + Tokq Bridge Ready (NATS leaf schema, frozen CLI)

5. **5 Tokq PRD gaps identified and closed:**
   - Gap 1 (FR-1, Agent Identity): `synlynk identity init` → Ed25519 keypair in v0.9.0
   - Gap 2 (FR-2/3, Memory Unit Schema): Section 3.1 mapping project-docs/ → Tokq units, frozen v1.0
   - Gap 3 (FR-4, ZK Encryption): AES-256-GCM via HKDF-SHA256, Tokq Alpha, `synlynk[tokq]` extra
   - Gap 4 (FR-5/7, Marketplace): `synlynk publish` / `subscribe` in Tokq Alpha
   - Gap 5 (FR-6, Ledger Boundary): costs.md = local (permanent), gas tank = cloud (additive). Coexist.

**Documents created/updated:**
- `docs/superpowers/specs/2026-06-06-synlynk-unified-roadmap.md` — canonical single source of truth
- `project-docs/roadmap.md` — replaced stale pre-Trio table with 9-release view
- `project-docs/todo.md` — 80+ discrete todos across v0.4→Tokq Alpha
- `project-docs/memory.md` — full rewrite with all 2026-06-06 decisions
- `docs/archive/` — 8 superseded proposals archived (consolidated-roadmap, multi-agent-impl-plan,
  agy-arch-review, public-launch-plan, agent-workers-assessment, agent-workers-git-managed,
  agent-perf, polyglot-bootstrap)
- `docs/brainstorm/synlynk-unified-roadmap/` — 6 visual companion HTML files committed

**Visual companion created:** 6 HTML pages at `docs/brainstorm/synlynk-unified-roadmap/`:
- `positioning-map.html` — 2x2 competitive map + capability matrix
- `os-framing.html` — OS layer stack diagram + release overview
- `tokq-convergence.html` — convergence map + product combination options
- `unified-vision.html` — origin story arc (Tokq→synlynk→unified)
- `unified-roadmap.html` — ecosystem coexistence map + five milestone roadmap
- `release-staircase.html` — full v0.3→v1.0 release staircase with infra arc

**Commits:** `a7fe8fc` (unified roadmap + archive + visuals), `f5ce10f` (5 Tokq gaps absorbed)

**Status:** Unified roadmap complete and committed. Ready to start v0.4.0 implementation planning.

**Next:** Invoke `superpowers:writing-plans` on the Trio Protocol spec
(`docs/superpowers/specs/2026-06-01-synlynk-trio-protocol-design.md`) to produce the v0.4.0
implementation plan.

## 2026-06-01
### Session: Trio Protocol Rearchitecture Brainstorm
- **Activity:** Deep review of current roadmap vs. three hybrid workgroup study papers (Claude, Codex,
  Gemini participant-observer analyses of the RxCC team). Brainstormed full rearchitecture of synlynk
  for solo human + emergent trio of AI agents.
- **Key Outcome:** Designed the **Trio Protocol** — two execution modes sharing a common core:
  - **Candidate 1 (Async):** `synlynk dispatch` → lightweight daemon → Architect→Build→Verify pipeline → interactive TUI review
  - **Candidate 2 (Sync):** `synlynk run` → foreground streaming, Ctrl+C interrupt → immediate TUI review. Plus `synlynk schedule` (OS-native + agent-native via Claude routines) and `synlynk queue`.
- **Core design decisions locked:**
  - Role assignment: emergent from usage (empirical scoring, no vendor defaults)
  - Domain tagging: keyword inference, `--domain` overrides
  - Cold-start routing: round-robin across all slots until 3 samples
  - Score decay: recency-weighted, default half-life = 10 tasks
  - Phase failure: auto-retry once with next-best agent, then halt
  - Verify: fully agent-driven (agent decides what to run; `test_cmd` injected as suggestion)
  - Review: interactive curses-based TUI
- **Revised roadmap:** v0.3.0 (Trio Bootstrap + Sync MVP) → v0.4.0 (Capability Engine) → v0.5.0
  (Async Mode + Full Pipeline) → v0.5.1 (Context Architecture) → v0.6.0 (Scheduled Autonomy) →
  v0.7.0 (TUI + Cost Observability) → v1.0.0 (Stable Trio)
- **Spec committed:** `docs/superpowers/specs/2026-06-01-synlynk-trio-protocol-design.md`
- **Status:** Parked. Spec approved, ready for implementation planning when resumed.
- **Next:** Invoke `superpowers:writing-plans` on the spec to produce the phased implementation plan.

## 2026-05-17
### Session: v0.2.1 Correctness Patch
- **Activity:** Received and evaluated external code review feedback on v0.2.0.
- **Review Findings:** Confirmed 5 bugs: exit code not propagated from `exec_command`, `parse_costs_md` reading wrong column (parts[6] vs parts[5]), `install.sh` version drift (1.2.0-lite vs 0.2.0), 3 dead functions never called, sparse `.gitignore`. Also stale roadmap.md.
- **TDD:** Wrote failing tests first for exit code propagation and costs schema mismatch before touching production code. Updated `conftest.py` fixture to match real `costs.md` 6-column schema.
- **Fixes shipped:** All 6 0.2.1 items — exit code propagation, costs parser column, dead code removal (`log_telemetry`, `extract_tokens`, `update_costs`), install.sh version, .gitignore expansion, roadmap refresh.
- **Milestone:** v0.2.1 merged to main via PR#3. 47 tests passing. `synlynk exec python3 -c 'sys.exit(7)'` now correctly exits 7 in shell.
- **Next:** v0.3.0 — subprocess CLI tests, checkpoint idempotency, `synlynk doctor`, shell completions.

## 2026-05-16
### Session: Product Definition Brainstorming
- **Activity:** Stepped back from implementation to define the long-term vision for synlynk.
- **Key Outcome:** Defined a two-tier strategy (Free/Solo and Paid/Team/Enterprise).
- **Solo Tier Vision:** A "Context Switchboard" for AI developers that manages context, projects, costs, models, and environments across various CLIs (Claude Code, Gemini, etc.) and IDEs (Cursor, VS Code).
- **Architectural Shift:** Moving from a simple template repository to a lightweight Local Context CLI/Daemon that uses MCP (Model Context Protocol) and wrapper scripts to maintain state across different AI engines.
- **Interoperability:** Focus on seamless context hand-offs between different AI tools (e.g., starting in Claude Code and finishing in Cursor).
- **Strategy Shift:** Adopted a "Lite vs Full" Free tier approach. Lite focuses on file-based context and shell wrappers; Full introduces the LCP Daemon and MCP Server.
- **Resolved Grilling Points:** 
    - Concurrency via Append-Only logs.
    - Telemetry via shell aliases.
    - Hallucination detection via process wrappers and context injection.
    - Shipping frequently with a built-in `upgrade` path.
- **Activity:** Created public README.md and scaffolded the initial `synlynk` CLI (v1.2.0-lite) in Python.
- **Milestone:** Established final brand identity as **synlynk**.
- **Activity:** Implemented `synlynk init` command in `bin/synlynk.py`.
- **Verification:** Verified `init` command successfully creates `project-docs/`, `.synlynk/`, and all template markdown files in a test environment.
- **Activity:** Implemented `synlynk exec` command in `bin/synlynk.py`.
- **Feature:** `exec` command now generates a unified `.synlynk/context.md` snapshot and captures execution telemetry (duration).
- **Verification:** Verified `exec` successfully aggregates project-docs and wraps terminal commands.
- **Activity:** Implemented `synlynk upgrade` simulation (auto-update path foundation).
- **Activity:** Added frictionless alias recommendations to `synlynk init` to encourage telemetry adoption.
- **Verification:** Verified `upgrade` and `init` (with tips) via manual execution.
- **Activity:** Implemented `install.sh` for global installation of the `synlynk` CLI to `~/.synlynk/bin`.
- **Feature:** Added a shebang to `bin/synlynk.py` to allow direct execution.
- **Verification:** Verified `install.sh` correctly installs the binary and provides PATH configuration instructions.
- **Activity:** Refined AI instructions in `GEMINI.md` and `CLAUDE.md` to prioritize the `.synlynk/context.md` snapshot.
- **Activity:** Implemented telemetry logging to `.synlynk/telemetry.json` (timestamp, command, duration, exit_code).
- **Activity:** Implemented the "Flatline" Sentinel (v0.1) to detect and flag 3 consecutive command failures.
- **Verification:** Verified telemetry and Sentinel detection via manual loop simulation in a test environment.
- **Activity:** Automated multi-environment PATH setup in `install.sh` for zsh, bash, and fish.
- **Feature:** `install.sh` now intelligently appends the `PATH` export to shell configuration files if not already present.
- **Milestone:** synlynk Lite installation is now a seamless "one-click" experience.
- **Activity:** Implemented token count extraction from CLI output in `synlynk exec`.
- **Feature:** `exec` now parses stdout for token patterns (Claude, Gemini, etc.) and automatically updates `project-docs/costs.md`.
- **Feature:** Added real-time cost estimation and session summary display after each command execution.
- **Feature:** Expanded `costs.md` to track Request Counts and aligned the template with professional observability standards.
- **Feature:** Implemented "Budget Pulse" in `exec_command` to show cumulative request totals alongside session costs.
- **Feature:** Added `.synlynk/config.json` for per-project budget configuration (USD and Request limits).
- **Feature:** Implemented runtime Budget Alerts (80% warning, 100% critical) for both cost and request counts.
- **Verification:** Verified request counting and pulse display via repeated command execution in a test environment.
- **Activity:** Standardized "Interoperability Protocol" by adding `AI_INSTRUCTIONS.md` and `.cursorrules` to the `init` templates.
- **Milestone:** synlynk Lite now supports "Quota-Hopping" across Claude, Gemini, Cursor, and Codex-based tools with shared context snapshots.
- **Verification:** Verified token parsing and cost logging via simulated CLI output.
- **Activity:** Discussed and defined architectural strategies for Context Compaction (Active vs. Archive) and Sub-Agent Context Routing (Task-scoped views).
- **Milestone:** Core "Lite Tier" infrastructure is verified and documented. Next phase focuses on token extraction and scaling strategies.
