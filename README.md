<p align="center">
  <img src="docs/img/logo/lockup.svg" alt="synlynk — keep your AI tools in sync" height="80">
</p>

<p align="center"><strong>Keep your AI tools in sync with your project.</strong></p>
<p align="center"><a href="https://synlynk.com">synlynk.com</a></p>

synlynk is a Python CLI that turns your terminal into a hybrid workgroup — one human, multiple AI agents, shared project state. It injects scoped project context into every agent dispatch, routes tasks to the best available agent using a live capability ledger, and tracks costs and hallucination loops. A shared `project-docs/` directory keeps every tool in sync: Claude Code, Codex, and AGY all read the same context, decisions, and progress.

**v0.9.4:** Context / Dispatch / Relay — SQLite-primary task state with generated `todo.md`, per-agent context profiles (`.agents/<agent>.json`), `synlynk jobs` reads live SQLite with `--watch`, pre-flight dispatch gate, HTTP SSE relay broker (`synlynk relay start/broadcast`), and VERIFY_SKIP sentinel pattern. 472 tests.

## Install

```bash
curl -sSL https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh | bash
```

Or run directly without installing:

```bash
python3 bin/synlynk.py <command>
```

**Requirements:** Python 3.8+, stdlib only — no dependencies.

## Quick start

```bash
# Initialize synlynk — discovers your agents, writes informed project-docs/
synlynk init

# Run an AI CLI with context automatically injected
synlynk exec claude
synlynk exec gemini

# Dispatch an agent job to run in the background
synlynk dispatch claude --task "refactor auth module"

# Check running jobs
synlynk jobs

# Tail a job's output
synlynk logs --job <job-id>

# Archive completed tasks and refresh context
synlynk checkpoint

# Show project state
synlynk status
```

## How it works

`synlynk exec <cmd>` does four things before handing off to your AI tool:

1. Reads `project-docs/memory.md`, `roadmap.md`, and `todo.md`
2. Writes a compacted snapshot to `.synlynk/context.md` — active tasks only, no completed items
3. Checks cumulative spend and request count against limits in `.synlynk/config.json`
4. After the session ends: detects flatline loops (3 consecutive failures of the same command) and writes alerts to `sentinel.md`

The AI tool is instructed (via `CLAUDE.md` / `GEMINI.md`) to read `context.md` at session start and to log costs manually to `project-docs/costs.md`. synlynk does not capture token usage automatically — cost tracking depends on the AI agent following the session protocol.

## Commands

| Command | Description |
| --- | --- |
| `synlynk init [--force]` | 6-step wizard: scans repo, discovers agents (Magic Moment 1), bootstraps `project-docs/`, offers LLM enrichment |
| `synlynk exec <cmd>` | Run any AI CLI with context injection and telemetry |
| `synlynk dispatch <agent> --task <text> [--story <id>] [--context-mode none\|task\|full]` | Dispatch an agent job to run in the background (Magic Moment 2) |
| `synlynk agent configure <name>` | Write `.agents/<name>.json` context profile interactively |
| `synlynk relay start [--port N]` | Start HTTP SSE relay broker in foreground (port 27472) |
| `synlynk relay broadcast <body> [--kind motd\|wellness\|message\|joke\|custom]` | Publish a broadcast event to the relay |
| `synlynk jobs [--all] [--watch]` | List jobs from SQLite (`--watch` refreshes every 2s) |
| `synlynk logs --job <id> [--tail N]` | Tail a job's stdout log |
| `synlynk shell [--story <id>]` | Open an interactive agent shell with story context |
| `synlynk launch <agent> [--story <id>]` | Prompt for task, then dispatch interactively |
| `synlynk run --trio <task>` | Dispatch the same task to all functional agents in parallel |
| `synlynk watch start\|stop\|status` | Background daemon that regenerates `context.md` on file changes (Unix only) |
| `synlynk checkpoint` | Archive completed `[x]` tasks to devlog, refresh context, emit telemetry |
| `synlynk status [--json]` | Dashboard: active tasks, budget, sentinel alerts, watcher state |
| `synlynk sentinel list\|clear [--severity] [--code]` | View or dismiss sentinel alerts |
| `synlynk scan [--deep] [--status]` | Scan source tree and inject `## Source Architecture` into context; `--deep` writes `state.db` + `project-docs/source-map.md`; `--status` shows cache age and counts |
| `synlynk identity init` | Create `~/.synlynk/identity.key` (Ed25519) and print public key |
| `synlynk upgrade` | Check GitHub releases for a newer version |
| `synlynk --version` | Print current version |

> **Note:** `synlynk watch` uses `os.fork()` and requires macOS or Linux. `synlynk dispatch` works on all platforms.

## synlynk init flags

| Flag | Default | Description |
|---|---|---|
| `--force` | off | Overwrite existing template files |
| `--agents claude,agy,codex` | all three | Comma-separated list of agents to generate instruction files for. `claude` → CLAUDE.md, `agy` → GEMINI.md, `codex` → AGENTS.md |
| `--mode solo\|team` | `solo` | Written to `project-docs/.synlynk_config.json`. Controls whether teammate devlogs appear in context |
| `--org <org>` | none | GitHub org name, stored in `.synlynk/config.json` |
| `--repo <repo>` | none | GitHub repo name, stored in `.synlynk/config.json` |
| `--project-id <id>` | none | GitHub Projects v2 node ID. When provided, fills the `TODO: PROJECT_ID` placeholder in all generated agent instruction files |

Example with all flags:

```bash
synlynk init --org acmecorp --repo api-server \
             --project-id PJ_kwDOA1234 \
             --agents claude,agy,codex \
             --mode team
```

## Project layout

```
project-docs/
  roadmap.md        # Feature priorities and status
  todo.md           # Active tasks ([ ] / [x] checkboxes with <!-- id: N --> comments)
  memory.md         # Persistent decisions and conventions
  costs.md          # Per-session cost log (maintained by the AI agent)
  devlogs/          # Per-user session notes (appended by checkpoint)

.synlynk/
  context.md        # Auto-generated snapshot (overwritten each exec/watch cycle)
  config.json       # Budget limits and settings
  telemetry.json    # Rolling log of last 100 exec/checkpoint/watch events
  state             # Current state: watching | active | stopped
  sentinel.md       # Flatline alerts
  watch.pid         # Watcher daemon PID (present only while running)
  watch.log         # Watcher daemon stdout/stderr
```

## Configuration

`.synlynk/config.json` (created by `synlynk init`):

```json
{
  "schema_version": 1,
  "budget": { "limit_usd": 10.0, "limit_requests": 100 },
  "watch_interval_seconds": 30,
  "org": null,
  "team": null,
  "sync_endpoint": null
}
```

`org`, `team`, and `sync_endpoint` are reserved for a future team sync feature and have no effect in the current version.

## Session protocol

`synlynk init` writes `CLAUDE.md`, `GEMINI.md`, and `AI_INSTRUCTIONS.md` to your repo root. At session start, the AI tool is instructed to:

1. Run `synlynk watch status` — start the watcher if stopped
2. Read `.synlynk/context.md` for full project state
3. Check `.synlynk/sentinel.md` for any active alerts
4. Report: last completed task, next active task, and (in team mode) recent teammate activity

At session end: append a devlog entry and run `synlynk checkpoint`.

## Budget tracking

synlynk warns at 80% of configured cost and request limits. Spend is read from `project-docs/costs.md`, which the AI agent is expected to update after each significant operation. The `exec` telemetry records duration and exit code but does not capture token counts automatically.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).

---

## Roadmap

synlynk's goal is to become the OS for multi-agent development — the substrate that keeps every AI tool, every agent, and every developer in sync across the full project lifecycle.

| Version | Theme | Status | Target |
|---|---|---|---|
| v0.3.x | Enriched agent templates, AGENTS.md, parametric init | ✅ Shipped | Jun 2026 |
| v0.4.x | Hybrid Workgroup Bootstrap — agent discovery, `dispatch`, `jobs`, `run --trio`, init wizard, instruction reach, task status model | ✅ Shipped | Jun 2026 |
| v0.5.0 | Capability Engine — data-driven agent routing, SQLite state | ✅ Shipped | Jun 2026 |
| v0.6.x | Job Control + Constraints — constraint propagation, job state machine, `synlynk pr check`, model version probes | ✅ Shipped | Jun 2026 |
| v0.7.0 | Static Scan Quality — `## Source Architecture` in every exec session, `synlynk scan`, 9-language symbol extraction | ✅ Shipped | Jun 2026 |
| v0.8.0 | Support Engineer Agent — 5 signal collectors, GH issue filing, draft fix PRs, `.agents/` config | ✅ Shipped | Jun 2026 |
| **v0.9.0** | Kernel Fixes + Package Split — scoped dispatch context, relevant files, verify contract, per-agent framing, Ed25519 signing, anti-gaming cap | ✅ Shipped | Jun 2026 |
| v0.9.1 | Install Hardening + Docs Migration — installed binary fix, `--docs-dir` flag, smart init migration | ✅ Shipped | Jun 2026 |
| **v0.9.2** | Team Onboarding + Consensus — `synlynk join`, `synlynk team status`, `synlynk decide`, pull-before-write arbitration, token budgets on stories | ✅ Shipped | Jun 2026 |
| v0.9.3 | Async Daemon — `synlynk daemon`, launchd/systemd, job queue, HTTP context server localhost:27471 | ✅ Shipped | Jun 2026 |
| **v0.9.4** | Context / Dispatch / Relay — SQLite task canon, agent profiles, `synlynk jobs` SQLite, HTTP SSE relay, VERIFY_SKIP sentinel | ✅ Shipped | Jun 2026 |
| v0.10.0 | Multi-Repo Workspace — `synlynk workspace init/join`, cross-repo epics | Planned | Aug 2026 |
| v1.0.0 | Community Layer — signed capability ledger, pipx/Homebrew, synlynk.com public launch | Planned | Sep 2026 |

**We're looking for community input on what to build next.** See the [Discussions](../../discussions) tab to vote on feature direction and share use cases.
