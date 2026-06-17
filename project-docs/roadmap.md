# synlynk Roadmap

**Positioning:** The OS for multi-agent development.  
**Spec:** `docs/superpowers/specs/2026-06-06-synlynk-unified-roadmap.md`

| Version | Theme | OS Layer | Infrastructure | Status | Target |
| :--- | :--- | :--- | :--- | :--- | :--- |
| v0.1–v0.3.0 | Kernel + Filesystem | exec · telemetry · flatline · budget · project-docs ledger · enriched templates | Flat files | ✅ Shipped | June 2026 |
| v0.3.1 | Sentinel + Observability Hardening | Token scraping restored · zombie/stall/quota/loop detection · burn rate · context bloat · sentinel severity + ack | Flat files | ✅ Shipped | June 2026 |
| v0.4.0 | Hybrid Workgroup Bootstrap | IPC — agent discovery, `synlynk dispatch`, job store (PID tracking), `synlynk jobs/logs/shell/run`, init wizard with Magic Moments | Flat files | ✅ Shipped | June 2026 |
| v0.4.1 | Instruction Reach | IDE reach — section markers (html/hash/none), `_write_instruction_file`, Cursor MDC · Copilot · Windsurf templates, SHA manifest, runtime drift detection (`INSTRUCTION_DRIFT` sentinel), `synlynk instructions status/diff/update/ack`; AGY replaces Gemini CLI; `DB_PATH` centralised to `~/.synlynk/projects/<hash>/state.db` | Flat files | ✅ Shipped | June 2026 |
| v0.4.2 | Task Status Model | Project state — 5-state `TASK_STATUSES` (`[ ]` active `[x]` done `[-]` deferred `[~]` superseded `[>]` absorbed); deferred tasks surfaced in context; checkpoint archives all resolved states; agent templates updated | Flat files | ✅ Shipped | June 2026 |
| v0.5.0 | Capability Engine | Scheduler — model-aware routing, 3D domain taxonomy (engg·org·industry), quality signal hierarchy (human→verifier→auto), `dispatch_rework` signal, `synlynk story/score` CLI, `state.db` SQLite ledger | **SQLite WAL** | ✅ Shipped | June 2026 |
| v0.6.0 | Job Control + Constraints | IPC complete — constraint propagation, job state machine · **+** model version tier-2 probe, `synlynk pr check`, `synlynk score attest`, verifier pipeline capture, Tokq `org_domain_tags` | SQLite extended | ✅ Shipped | June 2026 |
| v0.6.1 | Patch release | `VERSION` constant synced to GitHub releases (was perpetually behind); bundles v0.4.1 instruction reach + v0.4.2 task status model patches into a named release | Flat files | ✅ Shipped | June 2026 |
| v0.7.0 | Async Pipeline + Daemon | Shell — `synlynk dispatch`, daemon, `synlynk review` TUI | **HTTP Context Server** | Planned | Oct 2026 |
| v0.8.0 | Open Context Protocol | Ecosystem interface — `context --for`, `checkpoint --from`, MCP server | HTTP server (public) | Planned | Nov 2026 |
| v0.9.0 | Review TUI + Team Safety | Shell polish — full curses TUI, append-only event log, team guardrails | JSONL event log | Planned | Dec 2026 |
| v1.0.0 | Stable OS + Tokq Bridge Ready | Platform — frozen CLI, pipx/Homebrew, NATS leaf schema defined | **NATS leaf node schema** | Planned | Q1 2027 |
| Tokq Alpha | Cloud Bridge | Synlynk→Tokq sync over NATS leaf→hub | NATS + MessagePack | Planned | Q3 2027 |
| Tokq GA | Knowledge Marketplace | Agent identity, gas tank, publish/subscribe conventions | Full Tokq cloud | Planned | Q4 2027 |

## Strategic Initiatives (parallel tracks)

| Initiative | Theme | Agents | Status | Brainstorm |
| :--- | :--- | :--- | :--- | :--- |
| Synlynk Autopilot | Put synlynk's own growth, content, and QA on autonomous agents | PM (growth) · Marketing Intern (blogs + publishing) · Support Engineer (regression scanning) | 🧠 Brainstorm | `docs/proposals/synlynk-autopilot-initiative.md` |
