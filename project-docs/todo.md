# Project Todo List

<!-- Status: [ ] active  [x] done  [-] deferred  [~] superseded  [>] absorbed -->

## Completed (v0.1 – v0.8.0)
- [x] Core CLI: init, exec, upgrade, install.sh, telemetry, flatline, budget, token extraction <!-- id:0-9 -->
- [x] Enriched AI instruction templates (CLAUDE.md, GEMINI.md, AGENTS.md, AI_INSTRUCTIONS.md, Cursor MDC, Copilot, Windsurf) <!-- id:11,18 -->
- [x] Section marker system + SHA manifest + instruction drift detection + `synlynk instructions` CLI <!-- id:16-19d -->
- [x] DB_PATH centralised to `~/.synlynk/projects/<hash>/state.db` <!-- id:19e -->
- [x] 5-state task model `[ ] [x] [-] [~] [>]` + checkpoint archives <!-- id:28-29d -->
- [x] Capability engine: SQLite WAL, 3D domain taxonomy, quality signals, `synlynk story/score` CLI <!-- id:30-32 -->
- [x] Static source scanner: language-agnostic, `## Source Architecture` injection, `synlynk scan` CLI <!-- id: v0.7.0 -->
- [x] Support Engineer Agent: 5 signal collectors, 7/30-day dedup, foreground investigation, GH issue + draft PR, `.agents/` config system <!-- id: v0.8.0 -->

## Superseded by roadmap realignment 2026-06-21
- [~] Trio bootstrap: `synlynk trio init`, `synlynk run`, phase artifacts, domain inference <!-- id:20-27 — absorbed into broader dispatch model -->
- [~] Old v0.8.0 scope: async pipeline + daemon (now v0.9.2) <!-- id:50-55 -->
- [~] Old v0.9.0 scope: Open Context Protocol + MCP (now v1.3.0) <!-- id:60-66 -->
- [~] Old v1.0.0-rc scope: curses TUI, JSONL event log (absorbed into v0.9.2 daemon + v1.0.0) <!-- id:70-76 -->

## Deferred
- [-] `synlynk trio status` — routing matrix with scores <!-- id:33 -->
- [-] Shell completions: `synlynk completions <zsh|bash|fish>` <!-- id:35 -->
- [-] **HOTFIX** Issue #43: Normalise quality_auto when tests absent <!-- id:36 — address in v0.9.0 anti-gaming work -->
- [-] `synlynk constraint add/remove/list` — constraint propagation <!-- id:40 -->
- [-] `synlynk next` — recommend next task from todo.md <!-- id:44 — address in v0.9.1 join flow -->

---

## v0.8.1 — Security Guard (Maintainer)
- [ ] `.agents/security.json` — dep vulns, secret leaks, CVEs signal config <!-- id:100 -->
- [ ] `_collect_dependency_vulns` — run `pip-audit` or `npm audit`, parse JSON output <!-- id:101 -->
- [ ] `_collect_secret_scan` — regex scan staged/committed files for API keys, tokens <!-- id:102 -->
- [ ] Severity mapping: critical CVE → high, moderate → medium <!-- id:103 -->
- [ ] Tests: vuln collector, secret scan, dedup, engine integration <!-- id:104 -->
- [ ] GitHub Actions: `security-guard.yml` trigger on push + schedule <!-- id:105 -->

## v0.8.2 — Marketing Intern (Communicator)
- [ ] `.agents/marketing.json` — blog, release notes, social copy signal config <!-- id:110 -->
- [ ] `_collect_merged_prs` — list PRs merged since last run via `gh pr list --state merged` <!-- id:111 -->
- [ ] `_collect_milestone_signals` — detect version tags, release events <!-- id:112 -->
- [ ] Draft blog post generation via investigator dispatch <!-- id:113 -->
- [ ] Output: draft post to `docs/blog/drafts/` — human reviews before publish <!-- id:114 -->
- [ ] Tests: PR collector, milestone signal, dry-run no side effects <!-- id:115 -->

## v0.8.3 — PM Agent (Orchestrator)
- [ ] `.agents/pm.json` — growth signals, story routing, sprint pulse config <!-- id:120 -->
- [ ] `_collect_growth_signals` — GitHub stars velocity, clone counts, install rate <!-- id:121 -->
- [ ] `_collect_story_health` — stories blocked >3 days, no assignee, overdue estimates <!-- id:122 -->
- [ ] `_collect_sprint_pulse` — % stories in-progress vs done this week <!-- id:123 -->
- [ ] Sprint digest written to `project-docs/devlogs/pm-agent.md` <!-- id:124 -->
- [ ] Tests: growth collector, story health, sprint pulse <!-- id:125 -->

## v0.8.4 — Compliance Officer + Docs Keeper
- [ ] `.agents/compliance.json` — convention drift, instruction staleness <!-- id:130 -->
- [ ] `_collect_convention_drift` — diff current CLAUDE.md/GEMINI.md against SHA manifest <!-- id:131 -->
- [ ] `.agents/docs-keeper.json` — docs staleness relative to code changes <!-- id:132 -->
- [ ] `_collect_stale_docs` — files in `docs/` not touched in 30d while linked code changed <!-- id:133 -->
- [ ] Tests: drift detector, stale docs, both agents dry-run <!-- id:134 -->

---

## v0.9.0 — Kernel Fixes + Package Split
- [x] `generate_context(scope=task)` — scoped context slice; currently falls back to full (line ~2955) <!-- id:200 -->
- [x] Task → file-path mapping: inject `## Relevant Files` into dispatch prompt from source-map <!-- id:201 -->
- [x] Verify contract: inject `## How to verify: pytest tests/test_x.py` per dispatch <!-- id:202 -->
- [x] Per-agent dispatch framing: Codex (criteria+filelist) ≠ Claude (narrative) ≠ AGY (arg framing) <!-- id:203 -->
- [x] Wire Ed25519 signing into `_write_capability_rating` (col exists, signing not called) <!-- id:204 -->
- [x] Anti-gaming baseline: minimum complexity threshold in `quality_auto` scoring <!-- id:205 -->
- [x] **Package split:** `bin/synlynk.py` → `synlynk/` package (db · scan · context · instructions · dispatch · sentinel · daemon modules) <!-- id:206 -->
- [x] Update all imports, entry point, install.sh, tests after split <!-- id:207 -->
- [x] 365 tests passing after split (was 342 target) <!-- id:208 -->

## v0.9.1 — Team Onboarding + Consensus Framework ✅ Shipped as v0.9.2
- [x] `synlynk join` command: source scan → AI context files → devlog seed → team digest → task recommendation <!-- id:210 -->
- [x] Mature-project onboarding: read existing README/conventions/architecture before generating context files <!-- id:211 -->
- [x] `synlynk team status` — who's active (last devlog entry), in-progress stories, just-shipped <!-- id:212 -->
- [x] Pull-before-write arbitration: warn on concurrent edit conflict, don't hard-block <!-- id:213 -->
- [x] Token budgets at story creation: `synlynk story add` prompts `estimated_tokens` <!-- id:214 -->
- [x] PR merge audit: Support Engineer posts estimated vs actual token delta to PR description <!-- id:215 -->
- [x] `synlynk decide "<topic>" --panel <agents> [--record]` — consensus decision command <!-- id:216 -->
- [x] Decision record schema: `project-docs/decisions/YYYY-MM-DD-<slug>.md` + `decisions` table in state.db <!-- id:217 -->
- [x] Retroactively create Decision record for this roadmap realignment <!-- id:218 -->
- [x] Tests: join flow, team status, write-arbitration, decide command, decision record <!-- id:219 -->

## v0.9.2 — Async Daemon ✅ Shipped as v0.9.3 (PRs #56/#57/#58)
- [x] `synlynk daemon start/stop/status/restart` <!-- id:220 -->
- [x] launchd plist generation (macOS) + systemd unit generation (Linux) <!-- id:221 -->
- [x] Job queue persisted in `state.db` — survive daemon restarts <!-- id:222 -->
- [x] Crash recovery: resume from last completed phase artifact <!-- id:223 -->
- [x] HTTP context server on `localhost:27471` — serves `context.md` to local tools <!-- id:224 -->
- [x] Scheduled agent dispatch via daemon (replaces crontab entries from `--install-cron`) <!-- id:225 -->
- [x] Tests: daemon lifecycle, job queue persistence, crash recovery, context server <!-- id:226 -->

## v0.9.3 → **v0.9.4 in roadmap** — Workgroup Relay <!-- version drift: v0.9.1 install-hardening slip shifted numbering -->
- [ ] `synlynk relay join` — default path: connects to `relay.synlynk.com/<workspace-id>` (community relay); shows graceful "launching v1.0" if server not yet live, falls back to LAN <!-- id:230 -->
- [ ] mDNS announcement (Bonjour/Avahi) for LAN auto-discovery (fallback mode) <!-- id:231 -->
- [ ] Self-signed TLS cert auto-generated on first start (LAN mode) <!-- id:232 -->
- [ ] Daemon auto-connects to relay on discovery; offline queue → flush on reconnect <!-- id:233 -->
- [ ] Cloudflare Tunnel integration: `synlynk relay tunnel start` wraps `cloudflared tunnel` (hybrid/WFH teams) <!-- id:234 -->
- [ ] `synlynk relay self-host --fly` — deploy self-provisioned relay; requires `--enterprise` flag or exception token <!-- id:235 -->
- [ ] `synlynk relay upgrade` — migrate from LAN/CF Tunnel to community relay; update one URL <!-- id:235b -->
- [ ] `synlynk relay handover <member>` — revolving host protocol: signed broadcast, 10-min grace, degraded-mode warning <!-- id:236 -->
- [ ] `synlynk relay status` — connected members, host identity, events/min <!-- id:237 -->
- [ ] All events signed with member's Ed25519 identity <!-- id:238 -->
- [ ] Feature gate: `--enterprise` flag + exception token system for self-host path <!-- id:238b -->
- [ ] Tests: LAN discovery, offline queue, handover protocol, degraded-mode warning, community relay join, enterprise gate <!-- id:239 -->

---

## Onboarding Epic — Clarity, Discovery & First-Run Success
<!-- Onboarding is where users form (or fail to form) their mental model of synlynk. The confusion around modes, agent availability, and join semantics is structural: the model isn't established before the first command runs. -->

- [ ] **[OB-0] Onboarding journey map** — document the canonical paths for each persona before writing any code: (a) solo developer new to synlynk (no team, no existing repo); (b) developer joining a synlynk-enabled repo mid-project; (c) team lead adding synlynk to an active multi-human project; (d) agent/autopilot being onboarded to a project headlessly. For each: what is the first command? What do they need to know before they run it? What does success look like? Outcome: `docs/superpowers/specs/onboarding-journey-map.md` and updated `synlynk init` wizard flow. <!-- id:500 -->

- [ ] **[OB-1] Install → init → first exec clarity** — the canonical onboarding sequence is currently ambiguous. Specify and enforce an opinionated order: (1) `curl ... | bash` (install), (2) `cd <project> && synlynk init` (bootstrap project-docs + AI instruction files), (3) `synlynk daemon start` (prompted at end of init), (4) `synlynk agents status` (verify agent availability), (5) `synlynk exec <agent>` (first AI session). The `synlynk init` wizard should end with an explicit "next step" prompt rather than dropping the user at a shell. <!-- id:501 -->

- [ ] **[OB-2] `synlynk join` rewrite — single-repo clarity** — current `join` flow conflates initial onboarding with re-entry. Split into two distinct subcommands: `synlynk join` (first-time: source scan → context file generation → devlog seed → team digest → recommended first story) and `synlynk resume` (re-entry: show what changed since last session, active stories, teammates' recent devlog entries, next recommended task). Both commands should print an explicit "you're ready to start with: `synlynk exec <agent>`" close. <!-- id:502 -->

- [ ] **[OB-3] Multi-repo join — pre-v0.10 stopgap** — until `synlynk workspace` ships at v0.10.0, developers working across multiple repos with synlynk have no clear path: do they `synlynk init` in each repo independently? How do stories span repos? Define the current answer explicitly (yes, each repo is independent; cross-repo coordination is via shared devlog entries + explicit story references) and add it to the onboarding docs. Add a note in `synlynk join` output when a workspace-level config is detected in a parent directory. <!-- id:503 -->

- [ ] **[OB-4] Mode taxonomy rewrite** — replace the opaque `single|team` mode with a four-tier model that maps to real usage patterns: (a) `solo` — one human, no team features, no multi-user devlogs; (b) `solo+agents` — one human + configured AI agents, capability routing enabled, team features off; (c) `team` — multiple humans ± agents, full team features (devlogs per-user, pull-before-write, team status); (d) `team+agents` — full hybrid workgroup, all features on. Mode is set at `synlynk init` via a prompted question: "How will you be working?" with concrete examples. Stored in `.synlynk_config.json`. <!-- id:504 -->

- [ ] **[OB-5] Mode → agent availability relationship** — document and enforce: in `solo` mode, exec/dispatch work but team features (team status, devlog attribution, decide panels) are disabled; agents are available but appear in single-user context. In `solo+agents`, capability routing is active; agents have their own devlog entries and story assignments. In `team` and `team+agents`, agents are first-class team members indistinguishable from humans in the team status output. `synlynk team status` should show agents with their current story assignment, last-activity timestamp, and availability status. <!-- id:505 -->

- [ ] **[OB-6] Agent discovery — `synlynk agents` subcommand** — new command: `synlynk agents list` shows every known agent type (claude, codex, agy, gemini, copilot) with installation and configuration status. `synlynk agents status` shows availability state per configured agent. `synlynk agents describe <agent>` shows: supported domains, typical use cases, dispatch framing style, known limitations. This is the command a new user runs when they don't know which agent to use for their task. Output feeds into `synlynk dispatch` agent selection prompts. <!-- id:506 -->

- [ ] **[OB-7] Agent availability state machine** — define and track 5 availability states per agent: (1) NOT_INSTALLED (CLI not on PATH), (2) INSTALLED_NOT_CONFIGURED (CLI present, no valid API key or auth), (3) CONFIGURED_BUDGET_OK (ready for tasking), (4) CONFIGURED_BUDGET_LOW (>80% of limit consumed — warn, don't block), (5) CONFIGURED_QUOTA_THROTTLED (rate limit hit — show retry-after), (6) ACTIVE (currently running a dispatched job). State stored in `.synlynk/agent-state.json`, updated on each exec/dispatch and via `synlynk agents status` health check. Sentinel QUOTA_EXHAUSTED already exists — extend to cover NOT_CONFIGURED and pre-flight checks. <!-- id:507 -->

- [ ] **[OB-8] Progressive onboarding — activation steps model** — `synlynk init` currently generates 8+ files immediately. Reframe as a baseline + activation model: (a) baseline (always): `project-docs/` structure, `context.md`, minimal CLAUDE.md/GEMINI.md; (b) activate agents: `synlynk agents add <agent>` generates agent-specific instruction files + configures capability routing; (c) activate team: `synlynk team enable` switches mode to `team`, generates team-mode devlog + pull-before-write config; (d) activate daemon: `synlynk daemon start` (already exists); (e) activate relay: `synlynk relay join` (v0.9.4). Each activation step prints exactly what it created and what the next activation step is. <!-- id:508 -->

- [ ] **[OB-9] Onboarding health check — `synlynk doctor`** — new command that validates the current project's synlynk setup: checks project-docs completeness, daemon running state, agent availability (all 5 states), instruction file freshness (SHA manifest), budget headroom, sentinel alert backlog. Prints a clear pass/warn/fail per check with an actionable fix command. Modelled on `brew doctor` / `cargo check`. Runs automatically at end of `synlynk init` and `synlynk join`. <!-- id:509 -->

- [ ] **[OB-10] Re-entry flow — `synlynk resume`** — returning to a project after days/weeks away is a distinct use case from first-time join. `synlynk resume` (or `synlynk join --resume`): reads devlogs since last session, shows active stories + their current status, shows any sentinel alerts since last exec, shows team activity summary, recommends next action. Designed to answer "where was I?" in under 10 seconds. <!-- id:510 -->

- [ ] **[OB-11] First-run success metrics + OTel** — define success milestones and instrument them: M1 = `synlynk init` completed (project-docs generated), M2 = `synlynk daemon start` succeeded, M3 = first `synlynk exec` completed without error, M4 = first `synlynk dispatch` job completed (exit 0), M5 = first team member ran `synlynk join` (team mode). Milestone events emitted as OTel spans with `synlynk.onboarding.milestone` attribute. `synlynk doctor` shows which milestones have been reached. <!-- id:511 -->

- [ ] **[OB-12] Tests** — `synlynk doctor` pass/fail/warn per check, agent state transitions (all 5 states), mode switching, `synlynk resume` output with mocked devlog history, activation step progression, multi-repo detection in `synlynk join`. <!-- id:512 -->

---

## Agent Behaviour Epic — Instructions & Adherence
<!-- Instruction injection is currently fire-and-forget. This epic closes the loop: measure whether agents read, follow, and sustain standing instructions across all invocation modes. The cross-mode dataset is the Synlynk IDE justification story. -->

- [ ] **[AB-0] Access mode taxonomy** — enumerate all invocation surfaces and document instruction injection characteristics per mode: (a) `synlynk exec` (full context.md + instruction files injected), (b) `synlynk dispatch` headless (per-agent framing injected, no interactive session), (c) agent primary session with synlynk context (user-present, agent can self-service via daemon HTTP), (d) 3P IDEs (Cursor, Windsurf, Copilot — MDC/ruleset injection, no context.md pipeline), (e) direct API (no injection unless caller provides it), (f) future Synlynk IDE (guaranteed injection + adherence measurement). Outcome: `docs/superpowers/specs/agent-access-mode-matrix.md` <!-- id:400 -->

- [ ] **[AB-1] Instruction attach + compliance rate (exec path)** — measure whether agents acknowledge injected instructions in primary sessions. Three signals: (1) attach rate: did the agent reference or act on context.md contents (e.g., mentioned a constraint from memory.md, cited a roadmap item, followed a custom rule); (2) compliance rate: per-rule pass/fail for checkable rules (ran tests before commit, used correct branch naming, wrote blog post for PR, updated devlog); (3) instruction load latency: time from injection to first instruction-influenced action. Detect via output analysis + git state verification. <!-- id:401 -->

- [ ] **[AB-2] Instruction attach + compliance rate (dispatch/headless/3P IDE/API)** — same metrics for non-interactive modes. Headless dispatch: infer attach from whether agent followed the verify contract and per-agent framing. 3P IDE: compare sessions with synlynk MDC/ruleset against sessions without. API: baseline measurement of instruction-free behaviour. Output: per-mode compliance score table that feeds the Synlynk IDE justification dataset. <!-- id:402 -->

- [ ] **[AB-3] Compliance scoring framework + structured compliance tags** — define what compliance means per instruction class: (a) procedural rules (run tests, commit style, branch naming) — binary pass/fail from git/CI state; (b) contextual rules (use memory.md decisions, follow roadmap) — inferred from output; (c) behavioural rules (don't add unrequested features, no hallucinated endpoints) — sentinel-detected. Agents emit structured compliance tags in session output: `COMPLIANCE: tests_run=pass, branch_style=pass, context_referenced=pass`. Synlynk parses these in `check_sentinel_patterns()`. <!-- id:403 -->

- [ ] **[AB-4] Sentinel extension — instruction non-adherence patterns** — add new sentinel pattern classes to `check_sentinel_patterns()`: INSTRUCTION_DRIFT (agent output contradicts a standing rule from context.md), VERIFY_SKIP (dispatch completed but verify contract not satisfied), BRANCH_VIOLATION (commit landed on wrong branch), INSTRUCTION_IGNORE (agent explicitly acknowledges an instruction and then doesn't follow it), CONTEXT_STALE (agent references a decision that was superseded in memory.md). Each pattern fires an alert entry in `sentinel.md` with the specific rule violated. <!-- id:404 -->

- [ ] **[AB-5] Instruction durability — versioning + signed instructions** — extend the SHA manifest system to version-track instruction content, not just file presence. When compliance drops, correlate to the instruction version in effect at the time. Add Ed25519 signing to CLAUDE.md / GEMINI.md / AI_INSTRUCTIONS.md snapshots (same key infrastructure as capability ratings). Signed instructions let agents verify they have the canonical version, not a drift copy. Outcome: `synlynk instructions verify` command that checks signature + reports instruction age. <!-- id:405 -->

- [ ] **[AB-6] Instruction extensibility — per-agent overrides + gap detection** — define the instruction inheritance model: base instructions (AI_INSTRUCTIONS.md) → agent-specific overrides (CLAUDE.md, GEMINI.md, AGENTS.md) → story-level framing (dispatch context). Novel sentinel alerts that don't map to any standing instruction = instruction coverage gap; auto-draft a candidate instruction in `project-docs/decisions/draft-instruction-YYYY-MM-DD.md` for human review. Per-agent compliance variance (Codex follows verify contract at 90%, Agy at 70%) flags which agents need stronger or simpler framing. <!-- id:406 -->

- [ ] **[AB-7] Native behaviour availability matrix** — document which native agent capabilities are available per access mode: task tools (TaskCreate/TaskUpdate), /compact, /clear, goals/loops, web tools, file tools, MCP servers. Identify which synlynk capabilities fill gaps in non-primary modes: story/state.db ≈ TaskCreate, daemon checkpoint ≈ /compact, context.md injection ≈ persistent memory, sentinel ≈ loop/stall detection. For headless dispatch, add a `--capabilities` flag to `synlynk dispatch` so the agent receives an explicit "available tools in this session" list and doesn't attempt unavailable native commands. <!-- id:407 -->

- [ ] **[AB-8] Instruction effectiveness → capability ratings** — add `instruction_adherence_score` column to `capability_ratings` table. Every exec/dispatch session that has a compliance measurement contributes to this score alongside quality/speed/cost. Agents that follow instructions reliably in a domain score higher in that domain's routing. Instructions with consistently low attach rates are flagged in `synlynk instructions audit`. <!-- id:408 -->

- [ ] **[AB-9] Instruction injection audit log + cross-mode adherence dataset** — at every exec/dispatch, append to `.synlynk/instruction-audit.jsonl`: `{trace_id, timestamp, mode, agent, context_md_hash, instruction_files[], compliance_scores{}}`. After 30 sessions, `synlynk instructions stats` produces the cross-mode table: compliance rate by mode × agent × instruction class. This is the Synlynk IDE justification dataset — the quantitative case that Synlynk-native invocation produces measurably higher adherence than 3P IDE or raw API. <!-- id:409 -->

- [ ] **[AB-10] Tests + OTel instrumentation** — unit tests for each new sentinel pattern, compliance tag parser, instruction signature verify, per-agent variance detector. OTel attributes on exec/dispatch spans: `synlynk.instruction.attach_rate`, `synlynk.instruction.compliance_score`, `synlynk.instruction.drift_detected`, `synlynk.instruction.version`. <!-- id:410 -->

---

## Command Audit Epic — Command Health + OTel Instrumentation
<!-- Every synlynk command reviewed against a 9-dimension rubric; cross-cutting OTel tracer shipped as foundational infrastructure -->

- [ ] **[CA-0] Command inventory** — enumerate all commands + subcommands from `main()` argparse tree; produce a canonical table: command, short description, added in version, current status (stable/experimental/deprecated) <!-- id:310 -->
- [ ] **[CA-1] 9-dimension audit per command** — for every command, document: (1) when it makes sense to use, (2) hook/trigger conditions (git hooks, file-watch, CI, daemon schedule, manual), (3) pre-requisites (.synlynk/ present, AI CLI on PATH, daemon running, etc.), (4) input context consumed (context.md sections, SQLite tables, env vars), (5) skills/agents it can invoke, (6) output contract (stdout format, files written, DB rows changed, exit codes), (7) whether it can trigger an agent/autopilot downstream, (8) discoverability surface (--help text, context.md injection, site docs), (9) error UX when pre-reqs unmet. Outcome: `docs/superpowers/specs/command-audit-matrix.md` <!-- id:311 -->
- [ ] **[CA-2] Error UX sweep** — for every command with missing pre-reqs, replace cryptic tracebacks with structured error messages: `synlynk: not in a synlynk project. Run 'synlynk init' first.` / `synlynk: daemon not running. Start it with 'synlynk daemon start'.` Actionable message per failure mode. <!-- id:312 -->
- [ ] **[CA-3] Discoverability pass** — audit which commands appear in `synlynk --help` (all should), which are injected into `context.md` (agents need to know commands exist), which are on the site. Add missing entries. <!-- id:313 -->
- [ ] **[CA-4] OTel tracer — local-first** — implement a stdlib-only `SynlynkTracer` class: generates `trace_id` (UUID4) and `span_id` per invocation, records start/end times (time.perf_counter_ns), writes OTLP-compatible spans to `.synlynk/traces/YYYY-MM-DD.jsonl`. Span schema: `{trace_id, span_id, parent_span_id, name, start_ns, end_ns, attributes, status, error}`. <!-- id:314 -->
- [ ] **[CA-5] OTel instrumentation — all commands** — wrap every command's entry point in a root span; add child spans for sub-operations: `generate_context`, `agent_subprocess`, `sentinel_check`, `update_costs`, `dispatch_routing`, `daemon_poll_tick`. Attributes per span type (e.g. `agent`, `tokens_in`, `tokens_out`, `exit_code`, `story_id`, `files_changed`). <!-- id:315 -->
- [ ] **[CA-6] `synlynk telemetry` subcommand** — `synlynk telemetry tail` (live span stream from today's trace file), `synlynk telemetry stats` (command frequency, p50/p95 duration, error rate per command), `synlynk telemetry export --to <jaeger|otlp-http|stdout>` (push `.jsonl` to collector via HTTP, no SDK needed). Falls back to `opentelemetry-sdk` exporter if installed. <!-- id:316 -->
- [ ] **[CA-7] Hook wiring** — document and implement the standard hooks: `post-init` (daemon start prompt), `pre-exec` (budget check warning), `post-dispatch` (job-start banner), `post-merge-pr` (Marketing Intern trigger), `daemon-on-tick` (Support Engineer schedule). Wire into `.synlynk/hooks.json` config. <!-- id:317 -->
- [ ] **[CA-8] Autopilot trigger map** — for each command that can trigger an agent/autopilot, document the trigger contract: which story status transition, which signal, which agent archetype responds. Feeds into TPM Agent (v0.8.2) and PM Agent (v0.8.3) designs. <!-- id:318 -->
- [ ] **[CA-9] Command lifecycle labels** — add `@stable` / `@experimental` / `@deprecated` markers to each command's argparse `help=` string. Experimental commands print a one-line notice on use. Deprecated commands print a migration hint. <!-- id:319 -->
- [ ] **Tests** — tracer unit tests (span schema, parent linking, file rotation), telemetry CLI tests (stats output, export dry-run), hook wiring tests, error UX tests (each failure mode asserts correct message) <!-- id:320 -->

---

## DevX Epic — Synlynk Developer Experience (pre-v0.9.4)
<!-- These are design/strategy questions to resolve before v0.9.4 implementation begins -->

- [ ] **[DevX-1] Context-layer brainstorm for v0.9.4** — Run the brainstorm session from spec `docs/superpowers/specs/2026-06-24-v0.9.4-context-layer-design-question.md`. Key decisions: hybrid read in `generate_context()` (SQLite tasks + file memory), relay wire protocol (structured events, not markdown blob), `context.md` as backwards-compat view. <!-- id:300 -->
- [ ] **[DevX-2] Task tracking canon** — Decide and document the canonical source for open/allocated/in-progress tasks: `todo.md` (human-editable, git-tracked) vs `stories` table in `state.db` (machine-queryable) vs GitHub Projects V2 (PM view). Currently three sources exist with no declared winner. Outcome: written decision record in `project-docs/decisions/`. <!-- id:301 -->
- [ ] **[DevX-3] Dispatch lifecycle observability** — Design structured feedback for `synlynk dispatch` so users don't need to run status checks manually. Current gap: no proactive completion notification, no progress phases, no structured summary on finish. Proposed: job-start banner with ID, agent-emitted phase markers in log, daemon `/jobs/<id>` polling, terminal bell / OS notification on completion. Outcome: spec or implementation in v0.9.4. <!-- id:302 -->
- [ ] **[DevX-4] Usage model clarity** — Decide the canonical synlynk launch pattern and document it. Current reality: most users open a Claude/Codex/Agy session first and then ask for synlynk commands inside it (inverted from the design intent of `synlynk exec claude`). Questions: does CWD matter (project root vs parent)? Should we promote the daemon-first model? Should `synlynk exec` be framed differently? Outcome: updated CLAUDE.md / site copy / onboarding flow. <!-- id:303 -->

---

## v0.10.0 — Multi-Repo Workspace
- [ ] `synlynk workspace init <name>` — create workspace, register first repo <!-- id:250 -->
- [ ] `synlynk workspace join <name>` — add current repo to workspace <!-- id:251 -->
- [ ] `repos` table in state.db + `repo_id` FK on stories/events/costs <!-- id:252 -->
- [ ] Cross-repo Epic: one Epic spans N repos, stories have repo_id <!-- id:253 -->
- [ ] Workspace context slice: injected alongside per-repo context <!-- id:254 -->
- [ ] Relay extended to workspace scope (all repos share one relay) <!-- id:255 -->
- [ ] Support Engineer workspace mode: monitors all repos, cross-repo health signals <!-- id:256 -->
- [ ] Tests: workspace init/join, cross-repo epic, workspace context slice <!-- id:257 -->

---

## v1.0.0 — Community Layer: Local Workgroup + Public Launch
- [ ] Workgroup protocol: shared, signed capability ledger across humans + agents + autopilots <!-- id:260 -->
- [ ] SME archetype: event bus, domain-tag subscriptions, file-path triggers, non-mutating review job role <!-- id:261 -->
- [ ] `synlynk consult <sme-name> "<question>"` — explicit SME invocation <!-- id:262 -->
- [ ] Game-resistance hardened: review-weighted scoring, minimum complexity threshold <!-- id:263 -->
- [ ] Stable CLI contract + MIGRATION.md + `synlynk migrate` for pre-1.0 projects <!-- id:264 -->
- [ ] pipx distribution + Homebrew tap <!-- id:265 -->
- [ ] Cross-platform CI matrix (macOS Intel + Apple Silicon + Ubuntu LTS) <!-- id:266 -->
- [ ] synlynk.com live on independent hosting (Vercel/Netlify/Cloudflare Pages) <!-- id:267 -->
- [ ] Public blog live — Marketing Intern Autopilot maintains it <!-- id:268 -->
- [ ] Public launch (HN + Product Hunt) <!-- id:269 -->

---

## v1.1.0+ — Community Expansion
- [ ] v1.1: Relay → community server · cross-workgroup epics · agent entitlements at team level <!-- id:280 -->
- [ ] v1.2: Enterprise workspace · org-level governance agents · cross-team budget allocation <!-- id:281 -->
- [ ] v1.3: Domain/discipline communities · Tokq convergence · MCP / Open Context Protocol <!-- id:282 -->
- [ ] v1.3: Ed25519 identity → Tokq auth; `synlynk tokq connect/sync/balance` <!-- id:283 -->

---

## Research & Investigation
- [x] **VPS deep-dive brainstorm** — Fly.io for community relay + self-host; Hetzner budget enterprise option. Decision: community-first hybrid, self-host gated. Resolved 2026-06-21. <!-- id:290 -->
