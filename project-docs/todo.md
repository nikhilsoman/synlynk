# Project Todo List

## Completed (v0.1 – v0.3.0)
- [x] Implement core logic - `synlynk init` <!-- id: 0 --> [@nikhilsoman]
- [x] Implement `synlynk exec` wrapper for context injection <!-- id: 1 --> [@nikhilsoman]
- [x] Implement `synlynk upgrade` auto-update logic <!-- id: 2 --> [@nikhilsoman]
- [x] Implement `install.sh` for global installation <!-- id: 3 --> [@nikhilsoman]
- [x] Refine AI instructions (GEMINI.md, CLAUDE.md, AGENTS.md) <!-- id: 4 --> [@nikhilsoman]
- [x] Implement telemetry logging (`telemetry.json`) <!-- id: 5 --> [@nikhilsoman]
- [x] Implement flatline sentinel (hallucination detection) <!-- id: 6 --> [@nikhilsoman]
- [x] Add token count extraction from CLI outputs <!-- id: 7 --> [@nikhilsoman]
- [x] Add request counting and Budget Pulse summary <!-- id: 8 --> [@nikhilsoman]
- [x] Add per-project budget limit alerts <!-- id: 9 --> [@nikhilsoman]
- [x] Implement multi-environment PATH auto-setup <!-- id: 10 --> [@nikhilsoman]
- [x] Enrich init templates (CLAUDE.md, GEMINI.md, AGENTS.md, AI_INSTRUCTIONS.md) <!-- id: 11 --> [@nikhilsoman]
- [x] Add init flags: --agents, --mode, --org, --repo, --project-id <!-- id: 12 --> [@nikhilsoman]
- [x] Scan + maturity detection + SECTION_SIGNALS + GH ID extraction <!-- id: 13 --> [@nikhilsoman]
- [x] Unified roadmap + archive superseded proposals <!-- id: 14 --> [@nikhilsoman]

## v0.4.0 — Conventions + Trio Bootstrap
- [ ] Generate `project-docs/conventions.md` at `synlynk init` <!-- id: 20 --> [@nikhilsoman]
- [ ] Always inject conventions.md into context alongside memory/roadmap/todo <!-- id: 21 --> [@nikhilsoman]
- [ ] `synlynk trio init` — configure three named agent slots, write `.synlynk/trio.json` <!-- id: 22 --> [@nikhilsoman]
- [ ] `synlynk run "<task>"` — foreground Architect→Build→Verify pipeline <!-- id: 23 --> [@nikhilsoman]
- [ ] Phase artifact format: task-packet.md · build-notes.md · verify-report.md <!-- id: 24 --> [@nikhilsoman]
- [ ] Domain keyword inference from task description <!-- id: 25 --> [@nikhilsoman]
- [ ] Round-robin cold-start routing (first 3 samples per domain) <!-- id: 26 --> [@nikhilsoman]
- [ ] `synlynk doctor` — diagnose trio.json, conventions.md, agent CLIs <!-- id: 27 --> [@nikhilsoman]

## v0.5.0 — Capability Engine
- [ ] Migrate capability scores + telemetry to SQLite WAL (`.synlynk/state.db`) <!-- id: 30 --> [@nikhilsoman]
- [ ] Recency-weighted routing after 3 samples per (agent, phase, domain) <!-- id: 31 --> [@nikhilsoman]
- [ ] `synlynk score show / add / reset` <!-- id: 32 --> [@nikhilsoman]
- [ ] `synlynk trio status` — routing matrix with scores and sample counts <!-- id: 33 --> [@nikhilsoman]
- [ ] `synlynk cost add` — structured cost entry <!-- id: 34 --> [@nikhilsoman]
- [ ] Shell completions: `synlynk completions <zsh|bash|fish>` <!-- id: 35 --> [@nikhilsoman]

## v0.6.0 — Job Control + Constraints
- [ ] `synlynk constraint add/remove/list` — propagate to all agent contexts <!-- id: 40 --> [@nikhilsoman]
- [ ] SQLite job state machine (pending→architect→build→verify→awaiting_review→done) <!-- id: 41 --> [@nikhilsoman]
- [ ] `synlynk status / cancel / retry` <!-- id: 42 --> [@nikhilsoman]
- [ ] `synlynk context --task N / --changed` scoped context slices <!-- id: 43 --> [@nikhilsoman]
- [ ] `synlynk next` — recommend next task from todo.md <!-- id: 44 --> [@nikhilsoman]
- [ ] Auto-retry on phase failure (next-best agent, once) <!-- id: 45 --> [@nikhilsoman]

## v0.7.0 — Async Pipeline + Daemon
- [ ] `synlynk daemon start/stop/restart/status` (launchd / systemd) <!-- id: 50 --> [@nikhilsoman]
- [ ] `synlynk dispatch "<task>"` — async job submission <!-- id: 51 --> [@nikhilsoman]
- [ ] HTTP Context Server on `localhost:27471` <!-- id: 52 --> [@nikhilsoman]
- [ ] `synlynk review [<job-id>]` — curses TUI review bundle <!-- id: 53 --> [@nikhilsoman]
- [ ] `synlynk schedule add / queue add / queue run` <!-- id: 54 --> [@nikhilsoman]
- [ ] Daemon crash recovery from last completed phase artifact <!-- id: 55 --> [@nikhilsoman]

## v0.8.0 — Open Context Protocol
- [ ] `synlynk context --for <tool>` CLI shorthand <!-- id: 60 --> [@nikhilsoman]
- [ ] `synlynk checkpoint --from <tool>` CLI shorthand <!-- id: 61 --> [@nikhilsoman]
- [ ] `synlynk mcp start` — MCP server over stdio <!-- id: 62 --> [@nikhilsoman]
- [ ] Open Context Protocol spec published (standalone Markdown doc) <!-- id: 63 --> [@nikhilsoman]
- [ ] SuperPowers native integration skill <!-- id: 64 --> [@nikhilsoman]
- [ ] GStack context bridge <!-- id: 65 --> [@nikhilsoman]
- [ ] GitHub Actions sync gateway step <!-- id: 66 --> [@nikhilsoman]

## v0.9.0 — Review TUI + Team Safety + Agent Identity
- [ ] Full curses TUI with keyboard navigation (←/→, a=accept, r=reject, 1-5=rate) <!-- id: 70 --> [@nikhilsoman]
- [ ] Per-job cost roll-up in review header + costs.md <!-- id: 71 --> [@nikhilsoman]
- [ ] Append-only JSONL event log (`.synlynk/events.jsonl`) <!-- id: 72 --> [@nikhilsoman]
- [ ] Pull-before-write conflict detection in daemon <!-- id: 73 --> [@nikhilsoman]
- [ ] Attribution validation in team mode <!-- id: 74 --> [@nikhilsoman]
- [ ] `synlynk team status` rollup view <!-- id: 75 --> [@nikhilsoman]
- [ ] Textual TUI option behind `--ui textual` flag <!-- id: 76 --> [@nikhilsoman]
- [ ] `synlynk identity init` — generate UUID + Ed25519 keypair via ssh-keygen, write `.synlynk/identity.json` + `.synlynk/identity.key` <!-- id: 77 --> [@nikhilsoman]
- [ ] `synlynk identity show / rotate` commands <!-- id: 78 --> [@nikhilsoman]
- [ ] Auto-call `identity init` from `synlynk init` if no identity exists <!-- id: 79 --> [@nikhilsoman]

## v1.0.0 — Stable OS + Tokq Bridge Ready
- [ ] Freeze CLI/schema contract, add MIGRATION.md process <!-- id: 80 --> [@nikhilsoman]
- [ ] pipx distribution (pipx install synlynk) <!-- id: 81 --> [@nikhilsoman]
- [ ] Homebrew tap (brew install nikhilsoman/tap/synlynk) <!-- id: 82 --> [@nikhilsoman]
- [ ] `synlynk migrate` — in-place schema upgrade for pre-1.0 projects <!-- id: 83 --> [@nikhilsoman]
- [ ] Cross-platform CI matrix (macOS Intel + Apple Silicon + Ubuntu LTS) <!-- id: 84 --> [@nikhilsoman]
- [ ] NATS leaf node schema defined in `.synlynk/tokq.json` <!-- id: 85 --> [@nikhilsoman]
- [ ] Complete docs: CLI reference, project-docs schema, OCP spec, Trio spec, infra arc <!-- id: 86 --> [@nikhilsoman]
- [ ] Publish memory unit schema spec (`docs/tokq-memory-unit-schema.md`) and freeze it <!-- id: 85b --> [@nikhilsoman]
- [ ] `synlynk sync --dry-run` — show what would be sent without connecting <!-- id: 86b --> [@nikhilsoman]
- [ ] `synlynk tokq balance` stub (returns "not connected" until Tokq Alpha) <!-- id: 86c --> [@nikhilsoman]
- [ ] Public launch (HN + Product Hunt) <!-- id: 87 --> [@nikhilsoman]

## Tokq Alpha — Cloud Bridge + ZK Encryption + Marketplace
- [ ] `synlynk tokq connect` — Ed25519 challenge-response auth with Tokq, write connection token <!-- id: 90 --> [@nikhilsoman]
- [ ] ZK encryption layer: AES-256-GCM, key derived from Ed25519 via HKDF-SHA256, `pip install synlynk[tokq]` <!-- id: 91 --> [@nikhilsoman]
- [ ] `synlynk sync` — serialize project-docs/ → Tokq memory units, encrypt, push via NATS leaf <!-- id: 92 --> [@nikhilsoman]
- [ ] `synlynk sync --pull` — retrieve + decrypt + merge from Tokq <!-- id: 93 --> [@nikhilsoman]
- [ ] Auto-sync in daemon with `--tokq-sync-interval` option <!-- id: 94 --> [@nikhilsoman]
- [ ] `synlynk publish conventions` — package conventions.md as marketplace collection with metadata + pricing <!-- id: 95 --> [@nikhilsoman]
- [ ] `synlynk subscribe <collection-id>` — subscribe to published conventions, gas tank deduction <!-- id: 96 --> [@nikhilsoman]
- [ ] `synlynk tokq earnings` — show revenue from published collections (70/30 split) <!-- id: 97 --> [@nikhilsoman]
- [ ] Key rotation: `identity rotate` re-encrypts all memory units with new key <!-- id: 98 --> [@nikhilsoman]
