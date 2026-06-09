<p align="center">
  <img src="docs/img/logo/lockup.svg" alt="synlynk — keep your AI tools in sync" height="80">
</p>

<p align="center"><strong>Keep your AI tools in sync with your project.</strong></p>
<p align="center"><a href="https://synlynk.com">synlynk.com</a></p>

synlynk is a single-file Python CLI that injects project context into AI tool sessions, tracks costs, and detects hallucination loops. It maintains a shared `project-docs/` directory that every AI tool reads at session start — so switching between Claude Code, Gemini CLI, or Cursor doesn't lose your task state, decisions, or progress.

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
# Initialize synlynk in your repo
synlynk init

# Run an AI CLI with context automatically injected
synlynk exec claude
synlynk exec gemini

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
| `synlynk init [--force] [--agents ...] [--mode ...] [--org ...] [--repo ...] [--project-id ...]` | Bootstrap `project-docs/` and AI instruction files |
| `synlynk exec <cmd>` | Run any AI CLI with context injection and telemetry |
| `synlynk watch start\|stop\|status` | Background daemon that regenerates `context.md` when files change (Unix only) |
| `synlynk checkpoint` | Archive completed `[x]` tasks to devlog, refresh context, emit telemetry |
| `synlynk status [--json]` | Dashboard: active tasks, budget, sentinel alerts, watcher state |
| `synlynk upgrade` | Check GitHub releases for a newer version |
| `synlynk --version` | Print current version |

> **Note:** `synlynk watch` uses `os.fork()` and requires macOS or Linux.

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
| v0.3.0 | Conventions + enriched agent templates | ✅ Shipped | Jun 2026 |
| v0.4.0 | Trio Bootstrap — `synlynk run`, Architect→Build→Verify pipeline | 🔜 Next | Jul 2026 |
| v0.5.0 | Capability Engine — data-driven agent routing, SQLite state | Planned | Aug 2026 |
| v0.6.0 | Job Control — constraint propagation, job state machine | Planned | Sep 2026 |
| v0.7.0 | Async Pipeline + Daemon — `synlynk dispatch`, HTTP context server | Planned | Oct 2026 |
| v0.8.0 | Open Context Protocol — MCP server, cross-tool context API | Planned | Nov 2026 |
| v1.0.0 | Stable OS — frozen CLI, pipx/Homebrew, Tokq bridge ready | Planned | Q1 2027 |

**We're looking for community input on what to build next.** See the [Discussions](../../discussions) tab to vote on feature direction and share use cases.
