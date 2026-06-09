# synlynk Roadmap

**Positioning:** The OS for multi-agent development.  
**Spec:** `docs/superpowers/specs/2026-06-06-synlynk-unified-roadmap.md`

| Version | Theme | OS Layer | Infrastructure | Status | Target |
| :--- | :--- | :--- | :--- | :--- | :--- |
| v0.1–v0.3.0 | Kernel + Filesystem | exec · telemetry · flatline · budget · project-docs ledger · enriched templates | Flat files | ✅ Shipped | June 2026 |
| v0.4.0 | Conventions + Trio Bootstrap | IPC — shared rules, Architect→Build→Verify pipeline, `synlynk run` | Flat files | 🔜 Next | July 2026 |
| v0.5.0 | Capability Engine | Scheduler — data-driven routing, `capability.json` → SQLite | **SQLite WAL** | Planned | Aug 2026 |
| v0.6.0 | Job Control + Constraints | IPC complete — constraint propagation, job state machine | SQLite extended | Planned | Sep 2026 |
| v0.7.0 | Async Pipeline + Daemon | Shell — `synlynk dispatch`, daemon, `synlynk review` TUI | **HTTP Context Server** | Planned | Oct 2026 |
| v0.8.0 | Open Context Protocol | Ecosystem interface — `context --for`, `checkpoint --from`, MCP server | HTTP server (public) | Planned | Nov 2026 |
| v0.9.0 | Review TUI + Team Safety | Shell polish — full curses TUI, append-only event log, team guardrails | JSONL event log | Planned | Dec 2026 |
| v1.0.0 | Stable OS + Tokq Bridge Ready | Platform — frozen CLI, pipx/Homebrew, NATS leaf schema defined | **NATS leaf node schema** | Planned | Q1 2027 |
| Tokq Alpha | Cloud Bridge | Synlynk→Tokq sync over NATS leaf→hub | NATS + MessagePack | Planned | Q3 2027 |
| Tokq GA | Knowledge Marketplace | Agent identity, gas tank, publish/subscribe conventions | Full Tokq cloud | Planned | Q4 2027 |
