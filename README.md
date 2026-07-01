<p align="center">
  <img src="docs/img/logo/lockup.svg" alt="synlynk — keep your AI tools in sync" height="80">
</p>

<p align="center"><strong>Keep your AI tools in sync with your project.</strong></p>
<p align="center"><a href="https://synlynk.com">synlynk.com</a></p>

<p align="center">
  <a href="https://github.com/nikhilsoman/synlynk"><img src="https://img.shields.io/badge/tests-623%20passing-brightgreen" alt="Tests"></a>
  <a href="https://github.com/nikhilsoman/synlynk"><img src="https://img.shields.io/badge/version-0.9.8-blue" alt="Version"></a>
  <a href="https://github.com/nikhilsoman/synlynk"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://github.com/nikhilsoman/synlynk"><img src="https://img.shields.io/badge/python-3.9%2B-blue" alt="Python"></a>
</p>

synlynk is a Python CLI that turns your terminal into a hybrid workgroup — one human, multiple AI agents, shared project state. It injects scoped project context into every agent dispatch, routes tasks to the best available agent using a live capability ledger, and tracks costs and hallucination loops. A shared `project-docs/` directory keeps every tool in sync: Claude Code, Codex, and AGY all read the same context, decisions, and progress.

**v0.10.0:** FTUE onboarding with terminal-based Scan + Wizard, `state.db` centralized SQLite primary source of truth, one-shot project migration, direct `pipx` packaging, and updated capability tracking. 623 tests passing.

## Documentation

| | | |
|:---:|:---:|:---:|
| [![Official Reference](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/site/src/assets/img/docs/synlynk-official-reference-thumb.png)](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/docs/synlynk-official-reference.pdf) | [![Command Reference](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/site/src/assets/img/docs/synlynk-command-reference-thumb.png)](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/docs/synlynk-command-reference.pdf) | [![Quick Start Guide](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/site/src/assets/img/docs/synlynk-quickstart-guide-thumb.png)](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/docs/synlynk-quickstart-guide.pdf) |
| **[Official Reference](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/docs/synlynk-official-reference.pdf)** | **[Command Reference](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/docs/synlynk-command-reference.pdf)** | **[Quick Start Guide](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/docs/synlynk-quickstart-guide.pdf)** |
| 14-page full reference: architecture, all commands, agent profiles, relay, SQLite schema, changelog | 9-page command catalog: flags, options, usage scenarios | 5-page getting started: install, init, dispatch, invite |

## Install

**Recommended Method (via pipx):**
```bash
pipx install git+https://github.com/nikhilsoman/synlynk
```

**Alternative Method (via shell script):**
```bash
curl -sSL https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh | bash
```

**Run directly without installing:**
```bash
python3 bin/synlynk.py <command>
```

**Requirements:** Python 3.9+, stdlib only — no dependencies.

## Quick start

Get up and running in 60 seconds:

1. **Install synlynk globally:**
   ```bash
   pipx install git+https://github.com/nikhilsoman/synlynk
   ```

2. **Initialize your project:**
   Runs the interactive FTUE wizard to discover installed AI agent CLI tools, configure workspace topology, and bootstrap project state.
   ```bash
   synlynk init --wizard
   ```

3. **Analyze repository structure:**
   Scans the codebase to build and update the static source map.
   ```bash
   synlynk scan
   ```

4. **Migrate existing flat-file projects (optional):**
   If you have a project created using an older version of synlynk, migrate its `project-docs/` markdown files to `state.db`.
   ```bash
   synlynk migrate
   ```

5. **Dispatch a task to an agent in the background:**
   ```bash
   synlynk dispatch claude --task "refactor auth module"
   ```

6. **Check running jobs:**
   ```bash
   synlynk jobs
   ```

7. **Tail a job's output:**
   ```bash
   synlynk logs --job <job-id>
   ```

## How it works

At the core of synlynk is a dual-storage model designed for agent speed and Git reliability:

- **`state.db` is the permanent source of truth** for all project state, including stories, roadmaps, memories, devlogs, and costs.
- **`project-docs/` flat files are write-through backups.** Every write to `state.db` automatically updates the corresponding markdown files in `project-docs/` (e.g., `todo.md`, `roadmap.md`, `memory.md`, `costs.md`). This ensures a human-readable, Git-trackable record of project state.
- **`generate_context()` resolves state dynamically.** Once a project is migrated, it reads directly from the SQLite database to compile the current active context. For non-migrated repositories, it falls back to reading raw flat files.
- **`synlynk exec <cmd>` manages context injection.** Before handing off to your AI tool, it compiles the active tasks and decisions, writes a compacted snapshot to `.synlynk/context.md` (active tasks only, no completed items), and checks cumulative spend limits in `.synlynk/config.json`. After the session ends, it detects flatline loops (3 consecutive failures of the same command) and writes alerts to `sentinel.md`.

The AI tool is instructed (via `CLAUDE.md` / `GEMINI.md`) to read `.synlynk/context.md` at session start. Cost tracking is fully automated: `state.db` records costs to the `cost_entries` table, which are written through to `project-docs/costs.md`.

## Commands

| Command | Description |
| --- | --- |
| `synlynk init [--force] [--wizard]` | Runs the FTUE typeform-style TUI wizard (8 screens) to discover agents, configure workspace topology, and bootstrap project state. |
| `synlynk exec <cmd>` | Run any AI CLI with context injection and telemetry |
| `synlynk dispatch <agent> --task <text> [--story <id>] [--context-mode none\|task\|full]` | Dispatch an agent job to run in the background |
| `synlynk scan [--refresh] [--add path] [--remove path] [--dry-run] [--deep] [--status]` | Re-runnable repository analysis that scans the source tree and updates the source architecture context |
| `synlynk migrate [--dry-run] [--recover] [--setup-dr]` | One-shot import to migrate existing flat-file `project-docs/` to `state.db` |
| `synlynk memory add <section> <body>` | Add a memory/convention entry to `state.db` with write-through to the flat file |
| `synlynk devlog append <author> <date> <body>` | Append a devlog entry to `state.db` with write-through to the flat file |
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
| `synlynk identity init` | Create `~/.synlynk/identity.key` (Ed25519) and print public key |
| `synlynk upgrade` | Check GitHub releases for a newer version |
| `synlynk --version` | Print current version |

> **Note:** `synlynk watch` uses `os.fork()` and requires macOS or Linux. `synlynk dispatch` works on all platforms.

## synlynk init flags

| Flag | Default | Description |
|---|---|---|
| `--force` | off | Overwrite existing template files |
| `--wizard` | off | Run the TUI onboarding wizard (8 screens) |
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

### Post-Migration Layout
Once a project is migrated, all state is centralized in the `.synlynk/` directory:

```
.synlynk/
  state.db          # SQLite database (Source of truth for all project state)
  project-docs/     # Write-through backups (auto-updated on every DB write)
    roadmap.md      # Feature priorities and status
    todo.md         # Active tasks ([ ] / [x] checkboxes with <!-- id: N --> comments)
    memory.md       # Persistent decisions and conventions
    costs.md        # Per-session cost log (maintained by the AI agent)
    devlogs/        # Per-user session notes
  context.md        # Auto-generated snapshot (overwritten each exec/watch cycle)
  config.json       # Budget limits, DR sync path, and settings
  telemetry.json    # Rolling log of last 100 exec/checkpoint/watch events
  sentinel.md       # Flatline alerts
  state             # Current state: watching | active | stopped
  watch.pid         # Watcher daemon PID (present only while running)
  watch.log         # Watcher daemon stdout/stderr
```

> **Note:** Before migration, the `project-docs/` folder lives at the repository root (`/project-docs/`). Running `synlynk migrate` relocates it under `.synlynk/project-docs/` and registers the SQLite `state.db` as the primary source of truth.

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

synlynk warns at 80% of configured cost and request limits. Spend is recorded automatically in the `cost_entries` table of `state.db` (written through from every exec event) and the manual `project-docs/costs.md` markdown ledger is maintained as a write-through backup, ensuring a Git-trackable record of cumulative spend and request counts.

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
| **v0.10.0** | FTUE Scan + Wizard + state.db Migration + Packaging + README | ⚠️ In progress (Shipped when PR merges) | Jul 2026 |
| v1.0.0 | Community Layer — signed capability ledger, pipx/Homebrew, synlynk.com public launch | Planned | Sep 2026 |

**We're looking for community input on what to build next.** See the [Discussions](../../discussions) tab to vote on feature direction and share use cases.
