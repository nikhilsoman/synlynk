# Devlog - Nikhil Soman

## 2026-06-07
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
